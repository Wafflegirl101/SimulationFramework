import dearpygui.dearpygui as dpg
from .theme import apply_theme

from core import EventBus
from core.performance import PerformanceMonitor
from rendering import OpenGLRenderer
from viewport import SpacecraftViewport

from .dpg_input_source import DpgInputSource
from .layout import create_dockspace
from .spacecraft_designer import SpacecraftDesignerUI

CLICK_DRAG_TOLERANCE = 4.0  # pixels of movement still treated as a click


class DesignerApplication:
    """Wires the designer panel to the OpenGL spacecraft viewport."""

    def __init__(self):
        self.events = EventBus()
        self.renderer = OpenGLRenderer()
        self.performance = PerformanceMonitor()
        self.designer = SpacecraftDesignerUI(self.events)
        self.viewport = SpacecraftViewport(lambda: self.designer.spacecraft)
        self.input_source = None

        self._drag = None
        self._drag_distance = 0.0

        self.events.subscribe("spacecraft.updated", self._on_spacecraft_updated)
        self.events.subscribe("component.selected", self._on_component_selected)
        self.events.subscribe("view.explode", self._on_explode)
        self.events.subscribe("view.grid", self._on_grid)
        self.events.subscribe("view.reset_camera", self.viewport.reset_camera)

    @property
    def running(self):
        return True

    def initialize(self):
        apply_theme()
        create_dockspace()
        self.designer.build()
        self.input_source = DpgInputSource()
        self.viewport.invalidate(reframe=True)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_spacecraft_updated(self, spacecraft):
        if (
            self.viewport.selected_id is not None
            and spacecraft.get_component(self.viewport.selected_id) is None
        ):
            self.viewport.selected_id = None
        self.viewport.invalidate()

    def _on_component_selected(self, component_id):
        self.viewport.selected_id = component_id

    def _on_explode(self, amount):
        self.viewport.explode = amount
        self.viewport.invalidate()

    def _on_grid(self, visible):
        self.viewport.show_grid = visible

    # ------------------------------------------------------------------
    # Frame loop
    # ------------------------------------------------------------------

    def update(self):
        self.performance.update()
        if dpg.does_item_exist("fps_text"):
            dpg.set_value(
                "fps_text",
                f"{self.performance.fps:.0f} FPS · "
                f"{self.performance.frame_time:.1f} ms · {self.renderer.name}",
            )
        self._handle_input()

    def _handle_input(self):
        source = self.input_source
        over = source.is_cursor_over_viewport()
        dx, dy = source.mouse_delta()
        scroll = source.consume_scroll()
        camera = self.viewport.camera
        _, height = source.get_window_shape()

        if over and scroll:
            camera.zoom(scroll)

        if over and self._drag is None:
            for button in ("left", "right", "middle"):
                if source.is_clicked(button):
                    self._drag = button
                    self._drag_distance = 0.0
                    break

        if self._drag is not None:
            if source.is_down(self._drag):
                self._drag_distance += abs(dx) + abs(dy)
                if self._drag == "left":
                    camera.orbit(dx, dy)
                else:
                    camera.pan(dx, dy, height)
            else:
                if self._drag == "left" and self._drag_distance <= CLICK_DRAG_TOLERANCE:
                    x, y = source.get_cursor_pos()
                    self.designer.select_component(
                        self.viewport.pick(self.renderer, x, y)
                    )
                self._drag = None
        elif over and (dx or dy):
            x, y = source.get_cursor_pos()
            self.viewport.hovered_id = self.viewport.pick(self.renderer, x, y)
        elif not over:
            self.viewport.hovered_id = None

        if over and source.is_pressed("f"):
            self.viewport.invalidate(reframe=True)
        if over and source.is_pressed("r"):
            self.viewport.reset_camera()

    def render(self):
        self.renderer.begin_frame()
        self.viewport.render(self.renderer)
        self.renderer.end_frame()
