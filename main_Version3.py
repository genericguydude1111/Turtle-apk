from pathlib import Path
import time
from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, Ellipse, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

from game_logic import GameLogic, SKINS, ACHIEVEMENTS


class NoOpSound:
    def play(self):
        return None

    def stop(self):
        return None


class World(Widget):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.bind(size=lambda *_: self.redraw(), pos=lambda *_: self.redraw())

    def redraw(self):
        self.canvas.before.clear()
        g = self.app.game
        if not g:
            return
        with self.canvas.before:
            Color(*self.rgb(g.theme()["bg"]))
            Rectangle(pos=self.pos, size=self.size)
            # subtle grid
            Color(0.05, 0.10, 0.13, 0.8)
            step_y = int(dp(32))
            step_x = int(dp(40))
            for yy in range(0, int(self.height), step_y):
                Line(points=[self.x, self.y + yy, self.right, self.y + yy], width=0.5)
            for xx in range(0, int(self.width), step_x):
                Line(points=[self.x + xx, self.y, self.x + xx, self.top], width=0.5)
            if g.game_state != "PLAYING" or not g.all_path_steps:
                return

            # compute one uniform scale for mapping game coords to widget coords
            scale = min(self.width / 750.0, self.height / 750.0)
            cx = self.center_x
            cy = self.center_y

            def pos(p):
                x, y = p
                return (cx + x * scale, cy + y * scale)

            # path
            pts = []
            for p in g.all_path_steps:
                q = pos(p)
                pts += [q[0], q[1]]
            Color(*self.rgb(g.theme()["track"]))
            Line(points=pts, width=max(8, dp(28) * scale), cap="round", joint="round")

            Color(*self.rgb(g.theme()["line"]))
            for i in range(len(g.all_path_steps) - 1):
                a, b = g.all_path_steps[i], g.all_path_steps[i + 1]
                if b in g.visited_steps:
                    Line(points=[*pos(a), *pos(b)], width=max(2, dp(4) * scale))
                else:
                    Color(0.20, 0.29, 0.35, 1)
                    Line(points=[*pos(a), *pos(b)], width=max(2, dp(4) * scale))
                    Color(*self.rgb(g.theme()["line"]))

            # coins
            Color(1, 0.67, 0, 1)
            for c in g.coin_nodes:
                if c not in g.collected_coins:
                    q = pos(c)
                    r = dp(8) * max(0.6, scale)
                    Ellipse(pos=(q[0] - r, q[1] - r), size=(2 * r, 2 * r))

            # start/end
            for p, col in [
                (g.path_nodes[0]["pos"], (0.15, 0.68, 0.38, 1)),
                (g.path_nodes[-1]["pos"], (0.75, 0.24, 0.18, 1)),
            ]:
                q = pos(p)
                r = dp(16) * max(0.6, scale)
                Color(*col)
                RoundedRectangle(pos=(q[0] - r, q[1] - r), size=(2 * r, 2 * r), radius=[dp(5)])

            # turtle: shell + head + eye, using current skin
            q = pos(g.player_pos)
            r = dp(18) * max(0.6, scale)
            Color(*self.rgb(g.equipped_color()))
            Ellipse(pos=(q[0] - r, q[1] - r), size=(2 * r, 2 * r))
            Color(0.85, 0.95, 0.85, 1)
            Ellipse(pos=(q[0] + r * 0.45, q[1] - r * 0.45), size=(r * 0.9, r * 0.9))
            Color(0.05, 0.05, 0.05, 1)
            Ellipse(pos=(q[0] + r * 0.72, q[1] - r * 0.12), size=(dp(4), dp(4)))

    @staticmethod
    def rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)) + (1,)


class TurtlePathApp(App):
    title = "TURTLE PATH GAME"

    def build(self):
        self.game = GameLogic(self.user_data_dir)
        self.root = FloatLayout()
        self.world = World(self)
        self.root.add_widget(self.world)
        self.status = Label(
            text="",
            size_hint=(1, None),
            height=dp(80),
            pos_hint={"top": 1},
            font_size=sp(12),
            halign="left",
            valign="middle",
        )
        self.root.add_widget(self.status)
        self.message = Label(
            text="",
            size_hint=(0.9, None),
            height=dp(80),
            pos_hint={"center_x": 0.5, "center_y": 0.55},
            font_size=sp(20),
            bold=True,
        )
        self.root.add_widget(self.message)

        # audio with safe fallback
        self.audio = {}
        for name in ("beep", "boop", "ding", "coin", "achievement", "level_clear", "game_over", "step"):
            try:
                s = SoundLoader.load(str(Path(__file__).parent / "assets" / f"{name}.wav"))
                self.audio[name] = s if s else NoOpSound()
            except Exception:
                self.audio[name] = NoOpSound()

        Window.bind(on_key_down=self.on_key_down)

        # reduce default update rate to 10 FPS to save CPU on phones
        Clock.schedule_interval(self.tick, 1.0 / 10.0)

        self.show_menu()
        return self.root

    def sound(self, name):
        s = self.audio.get(name)
        try:
            if not s:
                return
            s.stop()
            s.play()
        except Exception:
            return

    def button(self, text, cb, **kwargs):
        b = Button(
            text=text,
            font_size=sp(14),
            bold=True,
            background_normal="",
            background_color=(0.10, 0.21, 0.28, 0.95),
            **kwargs,
        )
        b.bind(on_release=cb)
        return b

    def clear_overlays(self):
        for w in list(self.root.children):
            if getattr(w, "_overlay", False):
                self.root.remove_widget(w)

    # on-demand redraw helper
    def mark_dirty(self):
        Clock.schedule_once(lambda *_: self.refresh(), 0)

    def show_menu(self, *_):
        self.clear_overlays()
        self.game.game_state = "MENU"
        box = FloatLayout(size_hint=(0.92, 0.78), pos_hint={"center_x": 0.5, "center_y": 0.48})
        box._overlay = True
        title = Label(
            text="[b]🐢 TURTLE PATH GAME[/b]\n[size=14]HARDCORE ARCADE PATH[/size]",
            markup=True,
            font_size=sp(27),
            size_hint=(1, 0.25),
            pos_hint={"top": 0.98},
        )
        box.add_widget(title)
        best = Label(
            text=f"BEST: {self.game.save_data['high_score']}    🪙 COINS: {self.game.save_data['total_coins']}",
            font_size=sp(14),
            size_hint=(1, 0.12),
            pos_hint={"top": 0.72},
        )
        box.add_widget(best)
        for text, y, cb in [
            ("▶  START RUN", 0.52, self.start_run),
            ("🎨  SHOP", 0.36, self.show_shop),
            ("🏆  ACHIEVEMENTS", 0.22, self.show_achievements),
            ("📊  STATISTICS", 0.08, self.show_stats),
        ]:
            b = self.button(text, cb, size_hint=(0.72, 0.11), pos_hint={"center_x": 0.5, "y": y})
            box.add_widget(b)
        self.root.add_widget(box)
        self.status.text = ""
        self.message.text = ""
        self.mark_dirty()

    def start_run(self, *_):
        self.clear_overlays()
        self.game.start_new_run()
        self.add_game_controls()
        self.message.text = ""
        self.sound("beep")
        self.mark_dirty()

    def add_game_controls(self):
        # pause
        p = self.button("Ⅱ", self.pause, size_hint=(None, None), size=(dp(62), dp(52)), pos_hint={"right": 0.98, "top": 0.93})
        p._overlay = True
        self.root.add_widget(p)
        # directional pad
        buttons = [("▲", 90, 0.12, 0.20), ("▼", 270, 0.12, 0.04), ("◀", 180, 0.02, 0.12), ("▶", 0, 0.22, 0.12)]
        for text, h, x, y in buttons:
            b = self.button(text, lambda _, hh=h: self.step(hh), size_hint=(None, None), size=(dp(70), dp(60)), pos_hint={"x": x, "y": y})
            b._overlay = True
            self.root.add_widget(b)

    def step(self, h):
        result = self.game.try_step(h)
        ev = result.get("event")
        if ev == "mistake":
            self.sound("boop")
            self.flash("⚠️ CAREFUL!")
        elif ev == "stamina":
            self.sound("boop")
            self.flash("🔋 STAMINA EMPTY!")
        elif ev == "coin":
            self.sound("coin")
            self.flash("+ COIN!")
        elif ev == "clear":
            self.sound("level_clear")
            self.flash(f"🏁 LEVEL CLEAR!  +{result.get('bonus', 0)}")
        elif ev == "game_over":
            self.sound("game_over")
            self.flash("GAME OVER")
            Clock.schedule_once(lambda *_: self.show_game_over(), 0.35)
        else:
            self.sound("step")

        for item in result.get("unlocked", []):
            self.flash(f"🏆 {item[1]}")
            self.sound("achievement")

        if ev == "clear":
            Clock.schedule_once(lambda *_: (self.game.generate_new_level(), self.mark_dirty()), 0.85)

        self.mark_dirty()

    def flash(self, text):
        self.message.text = text
        Clock.unschedule(self.clear_message)
        Clock.schedule_once(self.clear_message, 0.8)

    def clear_message(self, *_):
        self.message.text = ""

    def pause(self, *_):
        if self.game.game_state == "PLAYING":
            self.game.game_state = "PAUSED"
            self.show_pause()
        elif self.game.game_state == "PAUSED":
            self.clear_overlays()
            self.game.game_state = "PLAYING"
            self.add_game_controls()
            self.mark_dirty()

    def show_pause(self, *_):
        self.clear_overlays()
        box = FloatLayout(size_hint=(0.82, 0.48), pos_hint={"center_x": 0.5, "center_y": 0.55})
        box._overlay = True
        box.add_widget(Label(text="[b]Ⅱ PAUSED[/b]", markup=True, font_size=sp(28), size_hint=(1, 0.3), pos_hint={"top": 1}))
        box.add_widget(self.button("▶  RESUME", self.pause, size_hint=(0.75, 0.22), pos_hint={"center_x": 0.5, "y": 0.36}))
        box.add_widget(self.button("🏠  QUIT RUN", self.show_menu, size_hint=(0.75, 0.22), pos_hint={"center_x": 0.5, "y": 0.08}))
        self.root.add_widget(box)
        self.mark_dirty()

    def show_game_over(self):
        self.clear_overlays()
        g = self.game
        box = FloatLayout(size_hint=(0.90, 0.78), pos_hint={"center_x": 0.5, "center_y": 0.48})
        box._overlay = True
        box.add_widget(
            Label(
                text=f"[b]💀 GAME OVER[/b]\n{g.last_death_reason}",
                markup=True,
                font_size=sp(23),
                size_hint=(1, 0.22),
                pos_hint={"top": 1},
            )
        )
        stats = f"SCORE {int(g.score)}    LEVEL {g.current_level}\nCOINS THIS RUN {g.run_coins}    STEPS {g.run_steps}\nMISTAKES {g.run_mistakes}"
        box.add_widget(Label(text=stats, font_size=sp(13), size_hint=(1, 0.24), pos_hint={"top": 0.73}))
        box.add_widget(self.button("🐢  PLAY AGAIN", self.start_run, size_hint=(0.78, 0.12), pos_hint={"center_x": 0.5, "y": 0.43}))
        box.add_widget(self.button("🎨  SHOP", self.show_shop, size_hint=(0.36, 0.10), pos_hint={"x": 0.07, "y": 0.27}))
        box.add_widget(self.button("🏆  ACHIEVEMENTS", self.show_achievements, size_hint=(0.48, 0.10), pos_hint={"right": 0.93, "y": 0.27}))
        box.add_widget(self.button("📊  STATISTICS", self.show_stats, size_hint=(0.52, 0.10), pos_hint={"center_x": 0.5, "y": 0.10}))
        self.root.add_widget(box)
        self.mark_dirty()

    def show_shop(self, *_):
        self.clear_overlays()
        self.game.game_state = "SHOP"
        box = FloatLayout(size_hint=(0.94, 0.9), pos_hint={"center_x": 0.5, "center_y": 0.48})
        box._overlay = True
        box.add_widget(Label(text=f"[b]🎨 TURTLE SHOP[/b]\n🪙 {self.game.save_data['total_coins']} coins", markup=True, font_size=sp(22), size_hint=(1, 0.14), pos_hint={"top": 1}))
        grid = GridLayout(cols=2, spacing=dp(8), padding=dp(8), size_hint=(0.92, 0.65), pos_hint={"center_x": 0.5, "top": 0.80})
        for sid, skin in SKINS.items():
            owned = sid in self.game.save_data["unlocked_skins"]
            label = f"{skin['name']}\n{'✓ EQUIPPED' if sid == self.game.save_data['equipped_skin'] else 'EQUIP' if owned else str(skin['cost']) + ' 🪙'}"
            b = self.button(label, lambda _, s=sid: self.shop_action(s), size_hint_y=None, height=dp(72))
            b.background_color = self.color4(skin["color"]) if owned else (0.10, 0.21, 0.28, 1)
            grid.add_widget(b)
        box.add_widget(grid)
        box.add_widget(self.button("◀ BACK", self.show_menu, size_hint=(0.55, 0.10), pos_hint={"center_x": 0.5, "y": 0.03}))
        self.root.add_widget(box)
        self.mark_dirty()

    def shop_action(self, sid):
        r = self.game.buy_or_equip_skin(sid)
        if r.get("event") == "not_enough":
            self.sound("boop")
            self.flash("🪙 NOT ENOUGH COINS!")
        else:
            self.sound("ding")
            self.flash(r.get("name", "EQUIPPED"))
        self.show_shop()

    def show_achievements(self, *_):
        self.clear_overlays()
        self.game.game_state = "ACHIEVEMENTS"
        box = FloatLayout(size_hint=(0.94, 0.9), pos_hint={"center_x": 0.5, "center_y": 0.48})
        box._overlay = True
        unlocked = len(self.game.save_data["achievements"])
        box.add_widget(Label(text=f"[b]🏆 ACHIEVEMENTS[/b]\n{unlocked}/{len(ACHIEVEMENTS)} unlocked", markup=True, font_size=sp(22), size_hint=(1, 0.13), pos_hint={"top": 1}))
        scroll = ScrollView(size_hint=(0.94, 0.67), pos_hint={"center_x": 0.5, "top": 0.82})
        grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for aid, (name, desc) in ACHIEVEMENTS.items():
            ok = aid in self.game.save_data["achievements"]
            grid.add_widget(Label(text=("✓ " if ok else "? ") + name + " — " + desc, color=(0, 1, 0.4, 1) if ok else (0.4, 0.45, 0.5, 1), size_hint_y=None, height=dp(38), font_size=sp(12)))
        scroll.add_widget(grid)
        box.add_widget(scroll)
        box.add_widget(self.button("◀ BACK", self.show_menu, size_hint=(0.55, 0.10), pos_hint={"center_x": 0.5, "y": 0.03}))
        self.root.add_widget(box)
        self.mark_dirty()

    def show_stats(self, *_):
        self.clear_overlays()
        self.game.game_state = "STATISTICS"
        box = FloatLayout(size_hint=(0.88, 0.88), pos_hint={"center_x": 0.5, "center_y": 0.48})
        box._overlay = True
        box.add_widget(Label(text="[b]📊 STATISTICS[/b]", markup=True, font_size=sp(23), size_hint=(1, 0.12), pos_hint={"top": 1}))
        scroll = ScrollView(size_hint=(0.9, 0.68), pos_hint={"center_x": 0.5, "top": 0.82})
        grid = GridLayout(cols=2, spacing=dp(3), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for name, val in self.game.stats():
            grid.add_widget(Label(text=name, size_hint_y=None, height=dp(34), font_size=sp(12)))
            grid.add_widget(Label(text=str(val), color=(0, 1, 0.4, 1), size_hint_y=None, height=dp(34), font_size=sp(12)))
        scroll.add_widget(grid)
        box.add_widget(scroll)
        box.add_widget(self.button("◀ BACK", self.show_menu, size_hint=(0.55, 0.10), pos_hint={"center_x": 0.5, "y": 0.03}))
        self.root.add_widget(box)
        self.mark_dirty()

    def refresh(self, *_):
        g = self.game
        if g.game_state == "PLAYING":
            elapsed = int(time.time() - g.level_start_time)
            self.status.text = f"BEST {g.save_data['high_score']}   LV {g.current_level}   🪙 {g.save_data['total_coins']}\nSCORE {int(g.score)}   ❤️ {g.lives}   🔋 {g.stamina}   🔥 {g.perfect_streak_counter}"
        self.world.redraw()

    def tick(self, dt):
        # keep tick lightweight; heavy redraws happen only when mark_dirty schedules refresh
        pass

    def on_key_down(self, window, key, scancode, codepoint, modifiers):
        if self.game.game_state != "PLAYING":
            return
        mapping = {119: 90, 115: 270, 97: 180, 100: 0, 273: 90, 274: 270, 276: 180, 275: 0}
        if key in mapping:
            self.step(mapping[key])
            return True
        if key == 112:
            self.pause()
            return True
        return False

    @staticmethod
    def color4(h):
        h = h.lstrip("#")
        return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)) + (1,)


if __name__ == "__main__":
    TurtlePathApp().run()