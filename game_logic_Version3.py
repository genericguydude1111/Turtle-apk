import json
import math
import random
import time
import traceback
from pathlib import Path

DEFAULT_SAVE = {
    "high_score": 0,
    "max_level": 1,
    "total_coins": 0,
    "unlocked_skins": ["neon"],
    "equipped_skin": "neon",
    "achievements": [],
    "games_played": 0,
    "games_finished": 0,
    "total_steps": 0,
    "total_mistakes": 0,
    "total_coins_collected": 0,
    "best_streak": 0,
    "best_run_score": 0,
    "best_run_level": 1,
    "longest_run_steps": 0,
}

SKINS = {
    "neon": {"name": "NEON", "color": "#00ff66", "cost": 0, "description": "The original turtle."},
    "aqua": {"name": "AQUA", "color": "#00fbff", "cost": 20, "description": "Cold-blooded cyber turtle."},
    "cyber": {"name": "CYBER", "color": "#cc00ff", "cost": 50, "description": "Straight from the neon grid."},
    "ruby": {"name": "RUBY", "color": "#ff3336", "cost": 100, "description": "Dangerously stylish."},
    "gold": {"name": "GOLD", "color": "#ffd700", "cost": 200, "description": "For turtles with expensive taste."},
    "platinum": {"name": "PLATINUM", "color": "#e8f0ff", "cost": 350, "description": "Shiny. Ridiculously shiny."},
    "toxic": {"name": "TOXIC", "color": "#b6ff00", "cost": 500, "description": "Probably shouldn't touch this turtle."},
    "ghost": {"name": "GHOST", "color": "#d9d9ff", "cost": 750, "description": "Spooky little speedless turtle."},
}

ACHIEVEMENTS = {
    "first_run": ("FIRST STEPS", "Play your first run."),
    "first_coin": ("SHINY!", "Collect your first coin."),
    "first_clear": ("PATHFINDER", "Clear your first level."),
    "no_mistakes": ("PERFECT RUN", "Clear a level without making a mistake."),
    "streak_10": ("ON FIRE", "Reach a 10-step streak."),
    "streak_20": ("UNSTOPPABLE", "Reach a 20-step streak."),
    "coins_10": ("COIN HOARDER", "Collect 10 coins in total."),
    "coins_50": ("TREASURE TURTLE", "Collect 50 coins in total."),
    "level_5": ("GETTING SERIOUS", "Reach level 5."),
    "level_10": ("HARDCORE", "Reach level 10."),
    "level_20": ("LEGENDARY TURTLE", "Reach level 20."),
    "score_1000": ("FOUR DIGITS", "Reach 1,000 points in one run."),
    "score_5000": ("ARCADE LEGEND", "Reach 5,000 points in one run."),
    "buy_skin": ("FASHION TURTLE", "Purchase a cosmetic skin."),
}

THEMES = [
    {"name": "NEON CITY", "bg": "#111a24", "track": "#2c3e50", "line": "#00fbff", "accent": "#00fbff"},
    {"name": "TOXIC FOREST", "bg": "#101f14", "track": "#1b331e", "line": "#00ff66", "accent": "#b6ff00"},
    {"name": "INFERNO", "bg": "#211110", "track": "#3b1d1a", "line": "#ff5500", "accent": "#ff3336"},
    {"name": "VOID", "bg": "#171020", "track": "#302044", "line": "#cc00ff", "accent": "#cc00ff"},
    {"name": "ICE GRID", "bg": "#0d1820", "track": "#203744", "line": "#8be9ff", "accent": "#ffffff"},
]


class GameLogic:
    """UI-independent game state. The original JSON save keys are preserved."""

    def __init__(self, data_dir=None):
        # support App.user_data_dir (string) or fallback to home directory
        if data_dir:
            try:
                self.save_dir = Path(str(data_dir))
            except Exception:
                self.save_dir = Path.home() / ".turtle_path_game"
        else:
            self.save_dir = Path.home() / ".turtle_path_game"

        self.save_path = self.save_dir / "turtle_runner_save.json"
        self.log_path = self.save_dir / "turtle_runner_error.log"
        self.save_data = self.load_game_data()

        # gameplay state
        self.score = 0
        self.current_level = 1
        self.stamina = 45
        self.lives = 3
        self.game_state = "MENU"
        self.level_start_time = time.time()
        self.run_start_time = time.time()
        self.levels_cleared_counter = 0
        self.perfect_streak_counter = 0
        self.run_steps = 0
        self.run_mistakes = 0
        self.run_coins = 0
        self.path_nodes = []
        self.all_path_steps = []
        self.visited_steps = set()
        self.coin_nodes = []
        self.collected_coins = set()
        self.floating_deltas = []
        self.last_death_reason = ""
        self.last_event_text = ""
        self.player_pos = (0, 0)
        self.player_heading = 0

    def _log(self, operation, exc):
        try:
            self.save_dir.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {operation}: {repr(exc)}\n")
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
        except Exception:
            # never raise from logging
            pass

    def load_game_data(self):
        data = {k: (v.copy() if isinstance(v, list) else v) for k, v in DEFAULT_SAVE.items()}
        try:
            self.save_dir.mkdir(parents=True, exist_ok=True)
            if not self.save_path.exists():
                return data
            raw = self.save_path.read_text(encoding="utf-8").strip()
            if not raw:
                return data
            if raw.startswith("{"):
                loaded = json.loads(raw)
                for key in data:
                    if key in loaded:
                        data[key] = loaded[key]
                if not isinstance(data.get("unlocked_skins"), list):
                    data["unlocked_skins"] = ["neon"]
                if not isinstance(data.get("achievements"), list):
                    data["achievements"] = []
                if data.get("equipped_skin") not in SKINS:
                    data["equipped_skin"] = "neon"
                return data
            old = raw.split(",")
            if len(old) >= 1:
                data["high_score"] = int(old[0])
            if len(old) >= 2:
                data["max_level"] = int(old[1])
            if len(old) >= 3:
                data["total_coins"] = int(old[2])
        except Exception as exc:
            self._log("load_game_data", exc)
        return data

    def save_game_data(self):
        try:
            self.save_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.save_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.save_data, indent=2), encoding="utf-8")
            tmp.replace(self.save_path)
            return True
        except Exception as exc:
            self._log("save_game_data", exc)
            return False

    def equipped_color(self):
        sid = self.save_data.get("equipped_skin", "neon")
        return SKINS.get(sid, SKINS["neon"])["color"]

    def theme(self):
        return THEMES[((self.current_level - 1) // 3) % len(THEMES)]

    def start_new_run(self):
        self.score = 0
        self.current_level = 1
        self.lives = 3
        self.stamina = 45
        self.levels_cleared_counter = 0
        self.perfect_streak_counter = 0
        self.run_steps = 0
        self.run_mistakes = 0
        self.run_coins = 0
        self.floating_deltas.clear()
        self.run_start_time = time.time()
        self.game_state = "PLAYING"
        self.save_data["games_played"] += 1
        self.save_game_data()
        self.generate_new_level()

    def generate_new_level(self):
        self.path_nodes = []
        self.all_path_steps = []
        self.visited_steps = set()
        self.coin_nodes = []
        self.collected_coins = set()
        self.floating_deltas.clear()
        self.lives = 3
        self.stamina = max(20, 50 - self.current_level * 2)
        self.level_start_time = time.time()

        grid = 100
        x, y = -300, -200
        self.path_nodes.append({"pos": (x, y), "heading": 0})
        visited = {(x, y)}
        directions = [(grid, 0, 0), (0, grid, 90), (-grid, 0, 180), (0, -grid, 270)]
        complexity = min(10, 4 + self.current_level // 2)
        attempts = random.randint(complexity, complexity + 2)
        for _ in range(attempts):
            valid = [
                (x + dx, y + dy, h)
                for dx, dy, h in directions
                if -300 <= x + dx <= 300 and -200 <= y + dy <= 200 and (x + dx, y + dy) not in visited
            ]
            if not valid:
                break
            nx, ny, heading = random.choice(valid)
            self.path_nodes[-1]["heading"] = heading
            self.path_nodes.append({"pos": (nx, ny), "heading": 0})
            visited.add((nx, ny))
            x, y = nx, ny

        for i in range(len(self.path_nodes) - 1):
            ax, ay = self.path_nodes[i]["pos"]
            bx, by = self.path_nodes[i + 1]["pos"]
            steps = 4
            for j in range(steps + 1):
                f = j / steps
                p = (int(round(ax + (bx - ax) * f)), int(round(ay + (by - ay) * f)))
                if p not in self.all_path_steps:
                    self.all_path_steps.append(p)

        if len(self.all_path_steps) > 5:
            possible = self.all_path_steps[2:-2]
            count = min(3 + self.current_level // 5, 5, len(possible))
            if count:
                self.coin_nodes = random.sample(possible, count)

        self.player_pos = self.path_nodes[0]["pos"]
        self.player_heading = self.path_nodes[0]["heading"]
        self.visited_steps.add(tuple(map(int, self.player_pos)))

    def _unlock(self, aid):
        if aid not in ACHIEVEMENTS or aid in self.save_data["achievements"]:
            return None
        self.save_data["achievements"].append(aid)
        self.save_game_data()
        return ACHIEVEMENTS[aid]

    def check_achievements(self):
        found = []
        checks = [
            ("first_run", self.save_data["games_played"] >= 1),
            ("first_coin", self.save_data["total_coins_collected"] >= 1),
            ("first_clear", self.levels_cleared_counter >= 1),
            ("no_mistakes", self.run_mistakes == 0 and self.levels_cleared_counter >= 1),
            ("streak_10", self.perfect_streak_counter >= 10),
            ("streak_20", self.perfect_streak_counter >= 20),
            ("coins_10", self.save_data["total_coins_collected"] >= 10),
            ("coins_50", self.save_data["total_coins_collected"] >= 50),
            ("level_5", self.current_level >= 5),
            ("level_10", self.current_level >= 10),
            ("level_20", self.current_level >= 20),
            ("score_1000", self.score >= 1000),
            ("score_5000", self.score >= 5000),
        ]
        for aid, ok in checks:
            if ok:
                item = self._unlock(aid)
                if item:
                    found.append((aid, item[0], item[1]))
        return found

    def collect_coin(self):
        x, y = self.player_pos
        for coin in self.coin_nodes:
            if coin not in self.collected_coins and abs(x - coin[0]) <= 4 and abs(y - coin[1]) <= 4:
                self.collected_coins.add(coin)
                self.save_data["total_coins"] += 1
                self.save_data["total_coins_collected"] += 1
                self.run_coins += 1
                self.floating_deltas.append(("+ COIN!", x, y, 0, "#ffaa00"))
                unlocked = self.check_achievements()
                self.save_game_data()
                return True, unlocked
        return False, []

    def try_step(self, heading):
        if self.game_state != "PLAYING":
            return {"event": "ignored", "unlocked": [], "value": 0}

        value = 0
        self.stamina -= 1
        self.run_steps += 1
        self.save_data["total_steps"] += 1
        self.player_heading = heading

        cx, cy = self.player_pos
        nx = int(round(cx + 25 * math.cos(math.radians(heading))))
        ny = int(round(cy + 25 * math.sin(math.radians(heading))))
        target = (nx, ny)

        # Valid move
        if target in self.all_path_steps:
            coin = False
            unlocked_total = []
            already_visited = target in self.visited_steps

            self.player_pos = target

            if not already_visited:
                self.visited_steps.add(target)
                value = 2 * self.current_level
                if self.perfect_streak_counter >= 20:
                    value += self.current_level
                elif self.perfect_streak_counter >= 10:
                    value += max(1, self.current_level // 2)

                self.score += value
                self.perfect_streak_counter += 1
                self.floating_deltas.append((f"+{value}", nx, ny, 0, "#00ff66"))

            coin, unlocked = self.collect_coin()
            if unlocked:
                unlocked_total.extend(unlocked)

            if self.score > self.save_data["high_score"]:
                self.save_data["high_score"] = int(self.score)
            self.save_data["best_streak"] = max(self.save_data["best_streak"], self.perfect_streak_counter)

            if self.stamina <= 0:
                self.lives -= 1
                self.run_mistakes += 1
                self.save_data["total_mistakes"] += 1
                self.perfect_streak_counter = 0
                if self.lives <= 0:
                    return self.game_over("Your stamina completely ran out!")
                self.player_pos = self.path_nodes[0]["pos"]
                self.stamina = max(20, 50 - self.current_level * 2)
                self.visited_steps = {tuple(map(int, self.player_pos))}
                self.save_game_data()
                return {"event": "stamina", "unlocked": unlocked_total, "value": value}

            fx, fy = self.path_nodes[-1]["pos"]
            required = max(1, len(self.all_path_steps) - 1)
            if abs(self.player_pos[0] - fx) <= 10 and abs(self.player_pos[1] - fy) <= 10 and len(self.visited_steps) >= required:
                return self.clear_current_level()

            self.save_data["best_run_score"] = max(self.save_data["best_run_score"], int(self.score))
            self.save_data["longest_run_steps"] = max(self.save_data["longest_run_steps"], int(self.run_steps))
            self.save_game_data()

            return {"event": "coin" if coin else "step", "unlocked": unlocked_total, "value": value}

        # Invalid move
        value = 2 * self.current_level
        self.score = max(0, self.score - value)
        self.lives -= 1
        self.run_mistakes += 1
        self.save_data["total_mistakes"] += 1
        self.perfect_streak_counter = 0
        if self.lives <= 0:
            return self.game_over("You lost all 3 lives!")
        self.save_game_data()
        return {"event": "mistake", "unlocked": self.check_achievements(), "value": 0}

    def clear_current_level(self):
        perfect = self.run_mistakes == 0
        bonus = 10 * self.current_level
        self.score += bonus
        self.levels_cleared_counter += 1
        self.save_data["games_finished"] += 1
        self.save_data["max_level"] = max(self.save_data["max_level"], self.current_level)
        self.save_data["high_score"] = max(self.save_data["high_score"], int(self.score))
        self.save_data["best_run_score"] = max(self.save_data["best_run_score"], int(self.score))
        self.save_data["best_run_level"] = max(self.save_data["best_run_level"], int(self.current_level))
        self.save_data["best_streak"] = max(self.save_data["best_streak"], int(self.perfect_streak_counter))
        self.save_game_data()
        unlocked = self.check_achievements()
        self.current_level += 1
        self.save_data["max_level"] = max(self.save_data["max_level"], self.current_level)
        unlocked += self.check_achievements()
        self.save_game_data()
        return {"event": "clear", "bonus": bonus, "next_level": self.current_level, "perfect": perfect, "unlocked": unlocked}

    def game_over(self, reason):
        self.game_state = "GAME_OVER"
        self.last_death_reason = reason
        self.save_data["high_score"] = max(self.save_data["high_score"], int(self.score))
        self.save_data["best_run_score"] = max(self.save_data["best_run_score"], int(self.score))
        self.save_data["best_run_level"] = max(self.save_data["best_run_level"], int(self.current_level))
        self.save_data["best_streak"] = max(self.save_data["best_streak"], int(self.perfect_streak_counter))
        self.save_data["longest_run_steps"] = max(self.save_data["longest_run_steps"], int(self.run_steps))
        self.save_game_data()
        return {"event": "game_over", "reason": reason, "unlocked": self.check_achievements()}

    def buy_or_equip_skin(self, skin_id):
        if skin_id not in SKINS:
            return {"event": "invalid"}
        skin = SKINS[skin_id]
        if skin_id in self.save_data["unlocked_skins"]:
            self.save_data["equipped_skin"] = skin_id
            self.save_game_data()
            return {"event": "equipped", "name": skin["name"]}
        if self.save_data["total_coins"] < skin["cost"]:
            return {"event": "not_enough", "cost": skin["cost"]}
        self.save_data["total_coins"] -= skin["cost"]
        self.save_data["unlocked_skins"].append(skin_id)
        self.save_data["equipped_skin"] = skin_id
        self.save_game_data()
        achievement = self._unlock("buy_skin")
        return {"event": "unlocked", "name": skin["name"], "achievement": achievement}

    def stats(self):
        return [
            ("Games Played", self.save_data["games_played"]),
            ("Levels Reached", self.save_data["max_level"]),
            ("Best Score", self.save_data["high_score"]),
            ("Total Coins", self.save_data["total_coins"]),
            ("Coins Collected", self.save_data["total_coins_collected"]),
            ("Total Steps", self.save_data["total_steps"]),
            ("Mistakes", self.save_data["total_mistakes"]),
            ("Best Streak", self.save_data["best_streak"]),
            ("Best Run Score", self.save_data["best_run_score"]),
            ("Best Run Level", self.save_data["best_run_level"]),
            ("Longest Run", self.save_data["longest_run_steps"]),
        ]