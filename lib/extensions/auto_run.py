# Authors: see git history
#
# Copyright (c) 2010 Authors
# Licensed under the GNU GPL version 3.0 or later.  See the file LICENSE for details.

import inkex

from ..elements import Stroke
from ..i18n import _
from ..stitches.auto_run import autorun
from .commands import CommandsExtension


class AutoRun(CommandsExtension):
    COMMANDS = ["trim"]

    def __init__(self, *args, **kwargs):
        CommandsExtension.__init__(self, *args, **kwargs)

        self.arg_parser.add_argument("-b", "--break_up", dest="break_up", type=str, default="")
        self.arg_parser.add_argument("-s", "--subdivide", dest="subdivide", type=float, default=0)
        self.arg_parser.add_argument("-p", "--preserve_order", dest="preserve_order", type=inkex.Boolean, default=False)
        self.arg_parser.add_argument("-o", "--options", dest="options", type=str, default="")
        self.arg_parser.add_argument("-i", "--info", dest="help", type=str, default="")

    def effect(self):
        elements = self.check_selection()
        if not elements:
            return

        starting_point = self.get_starting_point()
        ending_point = self.get_ending_point()

        break_up = self.options.break_up
        subdivide = self.options.subdivide if self.options.break_up == "subdivide" else None

        autorun(elements, self.options.preserve_order, break_up, subdivide, starting_point, ending_point)

    def get_starting_point(self):
        return self.get_point("satin_start")

    def get_ending_point(self):
        return self.get_point("satin_end")

    def get_point(self, command_type):
        command = None
        for stroke in self.elements:
            command = stroke.get_command(command_type)
            # select only the first occurence of
            if command:
                return command.target_point

    def check_selection(self):
        if not self.get_elements():
            return

        if not self.svg.selection:
            # L10N auto-route running stitch columns extension
            inkex.errormsg(_("Please select one or more stroke elements."))
            return False

        elements = [element for element in self.elements if isinstance(element, Stroke)]
        if len(elements) == 0:
            inkex.errormsg(_("Please select at least one stroke element."))
            return False

        return elements
