from hoverset.ui.widgets import Button, ToggleButton, Label
from hoverset.ui.icons import get_icon_image

from studio.ui.widgets import Pane
from studio.ui.tree import MalleableTreeView
from studio.feature.component_tree import ComponentTreeView
from studio.debugtools import common
from studio.debugtools.defs import RemoteWidget
from studio.i18n import _


class ElementTreeView(ComponentTreeView):

    class Node(MalleableTreeView.Node):
        # debugger widget to be ignored during loading
        # will be set at runtime
        debugger = None

        def __init__(self, master=None, **config):
            super().__init__(master, **config)
            self.widget = config.get("widget")
            setattr(self.widget, "_dbg_node", self)
            equiv = common.get_studio_equiv(self.widget)
            icon = equiv.icon if equiv else 'play'
            self.name_pad.configure(text=self.extract_name(self.widget))
            self.icon_pad.configure(image=get_icon_image(icon, 15, 15))
            self._loaded = False
            if not self.widget.winfo_ismapped():
                self.on_unmap()

        def on_map(self, *_):
            self.name_pad.configure(**self.style.text)

        def on_unmap(self, *_):
            self.name_pad.configure(**self.style.text_passive)

        @property
        def loaded(self):
            return self._loaded

        def update_preload_status(self, added):
            if self._loaded or self.widget.deleted:
                return
            if added or self.widget.winfo_children():
                # widget can expand
                self._set_expander(self.COLLAPSED_ICON)
            else:
                self._set_expander(self.BLANK)

        def extract_name(self, widget):
            if isinstance(widget, RemoteWidget):
                return str(widget._name).strip("!")
            return 'root'

        def load(self):
            # lazy loading
            # nodes will be loaded when parent node is expanded
            if self._loaded or self.widget.deleted:
                return
            for child in self.widget.winfo_children():
                if getattr(child, "_dbg_ignore", False):
                    continue
                self.add_as_node(widget=child).update_preload_status(False)
            self._loaded = True

        def expand(self):
            # load widgets first
            self.load()
            super().expand()

    def initialize_tree(self):
        super(ElementTreeView, self).initialize_tree()
        self._show_empty(_("No items detected"))

    def expand_to(self, widget):
        parent = widget.nametowidget(widget.winfo_parent())
        hierarchy = [parent]
        while parent:
            parent = parent.nametowidget(parent.winfo_parent())
            hierarchy.append(parent)
        hierarchy = hierarchy[:-1]
        for p in reversed(hierarchy):
            p._dbg_node.expand()

        assert hasattr(widget, "_dbg_node")
        return widget._dbg_node


class ElementPane(Pane):
    name = "Widget tree"
    display_name = _("Widget tree")
    MAX_STARTING_DEPTH = 4

    def __init__(self, master, debugger):
        super(ElementPane, self).__init__(master)
        self.debugger = debugger
        Label(self._header, **self.style.text_accent, text=self.display_name).pack(side="left")

        ElementTreeView.Node.debugger = debugger
        self._tree = ElementTreeView(self)
        self._tree.pack(side="top", fill="both", expand=True, pady=4)
        self._tree.allow_multi_select(True)
        self._tree.on_select(self.on_select)

        self._search_btn = Button(
            self._header, **self.style.button,
            image=get_icon_image("search", 15, 15), width=25, height=25,
        )
        self._search_btn.pack(side="right", padx=2)
        self._search_btn.on_click(self.start_search)

        self._reload_btn = Button(
            self._header, **self.style.button,
            image=get_icon_image("reload", 15, 15), width=25, height=25,
        )
        self._reload_btn.pack(side="right", padx=2)
        self._reload_btn.tooltip(_("reload tree"))

        self._toggle_btn = Button(
            self._header, image=get_icon_image("chevron_down", 15, 15),
            **self.style.button, width=25, height=25
        )
        self._toggle_btn.pack(side="right", padx=2)

        self._select_btn = ToggleButton(
            self._header, **self.style.button,
            image=get_icon_image("cursor", 15, 15), width=25, height=25,
        )
        self._select_btn.pack(side="right", padx=2)
        self._select_btn.on_change(self.debugger.set_hover)
        self._select_btn.tooltip(_("select element to inspect"))

        self._tree.add_as_node(widget=debugger.root).update_preload_status(False)

        self.debugger.bind("<<WidgetCreated>>", self.on_widget_created)
        self.debugger.bind("<<WidgetDeleted>>", self.on_widget_deleted)
        self.debugger.bind("<<WidgetModified>>", self.on_widget_modified)

    @property
    def selected(self):
        return self._tree.get()

    def on_select(self):
        self.debugger.selection.set(map(lambda node: node.widget, self._tree.get()))

    def on_widget_tap(self, widget, event):
        if widget:
            node = self._tree.expand_to(widget)
            if node:
                self._tree.see(node)
                node.select(event)

    def on_widget_created(self, _):
        widget = self.debugger.active_widget
        parent_node = getattr(widget.master, "_dbg_node", None)
        if parent_node:
            if parent_node.loaded:
                parent_node.add_as_node(widget=widget)
            else:
                parent_node.update_preload_status(True)

    def on_widget_deleted(self, _):
        widget = self.debugger.active_widget
        parent_node = getattr(widget.master, "_dbg_node", None)
        if parent_node:
            if parent_node.loaded:
                node = widget._dbg_node
                if node in self.selected:
                    self._tree.toggle_from_selection(node)
                    if not self.selected:
                        self._tree.see(self.debugger.root._dbg_node)
                parent_node.remove(widget._dbg_node)
            else:
                parent_node.update_preload_status(False)

    def on_widget_modified(self, _):
        if self.debugger.active_widget not in self.selected:
            return

    def on_widget_map(self, _):
        pass

    def on_widget_unmap(self, _):
        pass
