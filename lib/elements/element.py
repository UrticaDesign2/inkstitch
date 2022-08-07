# Authors: see git history
#
# Copyright (c) 2010 Authors
# Licensed under the GNU GPL version 3.0 or later.  See the file LICENSE for details.
import sys
from copy import deepcopy

import inkex
from inkex import bezier

from ..commands import find_commands
from ..debug import debug
from ..i18n import _
from ..marker import get_marker_elements_cache_key_data
from ..patterns import apply_patterns, get_patterns_cache_key_data
from ..svg import (PIXELS_PER_MM, apply_transforms, convert_length,
                   get_node_transform)
from ..svg.tags import INKSCAPE_LABEL, INKSTITCH_ATTRIBS
from ..utils import Point, cache
from ..utils.cache import get_stitch_plan_cache, CacheKeyGenerator


class Param(object):
    def __init__(self, name, description, unit=None, values=[], type=None, group=None, inverse=False,
                 options=[], default=None, tooltip=None, sort_index=0, select_items=None):
        self.name = name
        self.description = description
        self.unit = unit
        self.values = values or [""]
        self.type = type
        self.group = group
        self.inverse = inverse
        self.options = options
        self.default = default
        self.tooltip = tooltip
        self.sort_index = sort_index
        self.select_items = select_items

    def __repr__(self):
        return "Param(%s)" % vars(self)


# Decorate a member function or property with information about
# the embroidery parameter it corresponds to
def param(*args, **kwargs):
    p = Param(*args, **kwargs)

    def decorator(func):
        func.param = p
        return func

    return decorator


class EmbroideryElement(object):
    def __init__(self, node):
        self.node = node

        # update legacy embroider_ attributes to namespaced attributes
        legacy_attribs = False
        for attrib in self.node.attrib:
            if attrib.startswith('embroider_'):
                self.replace_legacy_param(attrib)
                legacy_attribs = True
        # convert legacy tie setting
        legacy_tie = self.get_param('ties', None)
        if legacy_tie == "True":
            self.set_param('ties', 0)
        elif legacy_tie == "False":
            self.set_param('ties', 3)

        # default setting for fill_underlay has changed
        if legacy_attribs and not self.get_param('fill_underlay', ""):
            self.set_param('fill_underlay', False)

    @property
    def id(self):
        return self.node.get('id')

    @classmethod
    def get_params(cls):
        params = []
        for attr in dir(cls):
            prop = getattr(cls, attr)
            if isinstance(prop, property):
                # The 'param' attribute is set by the 'param' decorator defined above.
                if hasattr(prop.fget, 'param'):
                    params.append(prop.fget.param)
        return params

    def replace_legacy_param(self, param):
        # remove "embroider_" prefix
        new_param = param[10:]
        if new_param in INKSTITCH_ATTRIBS:
            value = self.node.get(param, "").strip()
            self.set_param(param[10:], value)
        del self.node.attrib[param]

    @cache
    def get_param(self, param, default):
        value = self.node.get(INKSTITCH_ATTRIBS[param], "").strip()
        return value or default

    @cache
    def get_boolean_param(self, param, default=None):
        value = self.get_param(param, default)

        if isinstance(value, bool):
            return value
        else:
            return value and (value.lower() in ('yes', 'y', 'true', 't', '1'))

    @cache
    def get_float_param(self, param, default=None):
        try:
            value = float(self.get_param(param, default))
        except (TypeError, ValueError):
            value = default

        if value is None:
            return value

        if param.endswith('_mm'):
            value = value * PIXELS_PER_MM

        return value

    @cache
    def get_int_param(self, param, default=None):
        try:
            value = int(self.get_param(param, default))
        except (TypeError, ValueError):
            return default

        if param.endswith('_mm'):
            value = int(value * PIXELS_PER_MM)

        return value

    def set_param(self, name, value):
        param = INKSTITCH_ATTRIBS[name]
        self.node.set(param, str(value))

    @cache
    def _get_specified_style(self):
        # We want to cache this, because it's quite expensive to generate.
        return self.node.specified_style()

    def get_style(self, style_name, default=None):
        style = self._get_specified_style().get(style_name, default)
        if style == 'none':
            style = None
        return style

    @property
    @cache
    def stroke_scale(self):
        # How wide is the stroke, after the transforms are applied?
        #
        # If the transform is just simple scaling that preserves the aspect ratio,
        # then this is completely accurate.  If there's uneven scaling or skewing,
        # then the stroke is bent out of shape.  We'll make an approximation based on
        # the average scaling in the X and Y axes.
        #
        # Of course, transforms may also involve rotation, skewing, and translation.
        # All except translation can affect how wide the stroke appears on the screen.

        node_transform = inkex.transforms.Transform(get_node_transform(self.node))

        # First, figure out the translation component of the transform.  Using a zero
        # vector completely cancels out the rotation, scale, and skew components.
        zero = [0, 0]
        zero = inkex.Transform.apply_to_point(node_transform, zero)
        translate = Point(*zero)

        # Next, see how the transform affects unit vectors in the X and Y axes.  We
        # need to subtract off the translation or it will affect the magnitude of
        # the resulting vector, which we don't want.
        unit_x = [1, 0]
        unit_x = inkex.Transform.apply_to_point(node_transform, unit_x)
        sx = (Point(*unit_x) - translate).length()

        unit_y = [0, 1]
        unit_y = inkex.Transform.apply_to_point(node_transform, unit_y)
        sy = (Point(*unit_y) - translate).length()

        # Take the average as a best guess.
        node_scale = (sx + sy) / 2.0

        return node_scale

    @property
    @cache
    def stroke_width(self):
        width = self.get_style("stroke-width", "1.0")
        width = convert_length(width)
        return width * self.stroke_scale

    @property
    @param('ties',
           _('Allow lock stitches'),
           tooltip=_('Tie thread at the beginning and/or end of this object. Manual stitch will not add lock stitches.'),
           type='dropdown',
           # Ties: 0 = Both | 1 = Before | 2 = After | 3 = Neither
           # L10N options to allow lock stitch before and after objects
           options=[_("Both"), _("Before"), _("After"), _("Neither")],
           default=0,
           sort_index=50)
    @cache
    def ties(self):
        return self.get_int_param("ties", 0)

    @property
    @param('force_lock_stitches',
           _('Force lock stitches'),
           tooltip=_('Sew lock stitches after sewing this element, '
                     'even if the distance to the next object is shorter than defined by the collapse length value in the Ink/Stitch preferences.'),
           type='boolean',
           default=False,
           sort_index=51)
    @cache
    def force_lock_stitches(self):
        return self.get_boolean_param('force_lock_stitches', False)

    @property
    def path(self):
        # A CSP is a  "cubic superpath".
        #
        # A "path" is a sequence of strung-together bezier curves.
        #
        # A "superpath" is a collection of paths that are all in one object.
        #
        # The "cubic" bit in "cubic superpath" is because the bezier curves
        # inkscape uses involve cubic polynomials.
        #
        # Each path is a collection of tuples, each of the form:
        #
        # (control_before, point, control_after)
        #
        # A bezier curve segment is defined by an endpoint, a control point,
        # a second control point, and a final endpoint.  A path is a bunch of
        # bezier curves strung together.  One could represent a path as a set
        # of four-tuples, but there would be redundancy because the ending
        # point of one bezier is the starting point of the next.  Instead, a
        # path is a set of 3-tuples as shown above, and one must construct
        # each bezier curve by taking the appropriate endpoints and control
        # points.  Bleh. It should be noted that a straight segment is
        # represented by having the control point on each end equal to that
        # end's point.
        #
        # In a path, each element in the 3-tuple is itself a tuple of (x, y).
        # Tuples all the way down.  Hasn't anyone heard of using classes?

        if getattr(self.node, "get_path", None):
            d = self.node.get_path()
        else:
            d = self.node.get("d", "")

        if not d:
            self.fatal(_("Object %(id)s has an empty 'd' attribute.  Please delete this object from your document.") % dict(id=self.node.get("id")))

        return inkex.paths.Path(d).to_superpath()

    @cache
    def parse_path(self):
        return apply_transforms(self.path, self.node)

    @property
    @cache
    def paths(self):
        return self.flatten(self.parse_path())

    @property
    def shape(self):
        raise NotImplementedError("INTERNAL ERROR: %s must implement shape()", self.__class__)

    @property
    @cache
    def commands(self):
        return find_commands(self.node)

    @cache
    def get_commands(self, command):
        return [c for c in self.commands if c.command == command]

    @cache
    def has_command(self, command):
        return len(self.get_commands(command)) > 0

    @cache
    def get_command(self, command):
        commands = self.get_commands(command)

        if commands:
            return commands[0]
        else:
            return None

    def strip_control_points(self, subpath):
        return [point for control_before, point, control_after in subpath]

    def flatten(self, path):
        """approximate a path containing beziers with a series of points"""

        path = deepcopy(path)
        bezier.cspsubdiv(path, 0.1)

        return [self.strip_control_points(subpath) for subpath in path]

    def flatten_subpath(self, subpath):
        path = [deepcopy(subpath)]
        bezier.cspsubdiv(path, 0.1)

        return self.strip_control_points(path[0])

    @property
    def trim_after(self):
        return self.get_boolean_param('trim_after', False)

    @property
    def stop_after(self):
        return self.get_boolean_param('stop_after', False)

    def to_stitch_groups(self, last_patch):
        raise NotImplementedError("%s must implement to_stitch_groups()" % self.__class__.__name__)

    @debug.time
    def _load_cached_stitch_groups(self, previous_stitch):
        if not self.uses_previous_stitch():
            # we don't care about the previous stitch
            previous_stitch = None

        cache_key = self._get_cache_key(previous_stitch)
        stitch_groups = get_stitch_plan_cache().get(cache_key)

        if stitch_groups:
            debug.log(f"used cache for {self.node.get('id')} {self.node.get(INKSCAPE_LABEL)}")
        else:
            debug.log(f"did not use cache for {self.node.get('id')} {self.node.get(INKSCAPE_LABEL)}, key={cache_key}")

        return stitch_groups

    def uses_previous_stitch(self):
        """Returns True if the previous stitch can affect this Element's stitches.

        This function may be overridden in a subclass.
        """
        return False

    @debug.time
    def _save_cached_stitch_groups(self, stitch_groups, previous_stitch):
        stitch_plan_cache = get_stitch_plan_cache()
        cache_key = self._get_cache_key(previous_stitch)
        if cache_key not in stitch_plan_cache:
            stitch_plan_cache[cache_key] = stitch_groups

        if previous_stitch is not None:
            # Also store it with None as the previous stitch, so that it can be used next time
            # if we don't care about the previous stitch
            cache_key = self._get_cache_key(None)
            if cache_key not in stitch_plan_cache:
                stitch_plan_cache[cache_key] = stitch_groups

    def get_params_and_values(self):
        params = {}
        for param in self.get_params():
            params[param.name] = self.get_param(param.name, param.default)

        return params

    @cache
    def _get_patterns_cache_key_data(self):
        return get_patterns_cache_key_data(self.node)

    @cache
    def _get_guides_cache_key_data(self):
        return get_marker_elements_cache_key_data(self.node, "guide-line")

    def _get_cache_key(self, previous_stitch):
        cache_key_generator = CacheKeyGenerator()
        cache_key_generator.update(self.__class__.__name__)
        cache_key_generator.update(self.get_params_and_values())
        cache_key_generator.update(self.parse_path())
        cache_key_generator.update(list(self._get_specified_style().items()))
        cache_key_generator.update(previous_stitch)
        cache_key_generator.update([(c.command, c.target_point) for c in self.commands])
        cache_key_generator.update(self._get_patterns_cache_key_data())
        cache_key_generator.update(self._get_guides_cache_key_data())

        cache_key = cache_key_generator.get_cache_key()
        debug.log(f"cache key for {self.node.get('id')} {self.node.get(INKSCAPE_LABEL)} {previous_stitch}: {cache_key}")

        return cache_key

    def embroider(self, last_stitch_group):
        debug.log(f"starting {self.node.get('id')} {self.node.get(INKSCAPE_LABEL)}")
        if last_stitch_group:
            previous_stitch = last_stitch_group.stitches[-1]
        else:
            previous_stitch = None
        stitch_groups = self._load_cached_stitch_groups(previous_stitch)

        if not stitch_groups:
            self.validate()

            stitch_groups = self.to_stitch_groups(last_stitch_group)
            apply_patterns(stitch_groups, self.node)

            for stitch_group in stitch_groups:
                stitch_group.tie_modus = self.ties
                stitch_group.force_lock_stitches = self.force_lock_stitches

            if stitch_groups:
                stitch_groups[-1].trim_after = self.has_command("trim") or self.trim_after
                stitch_groups[-1].stop_after = self.has_command("stop") or self.stop_after

            self._save_cached_stitch_groups(stitch_groups, previous_stitch)

        debug.log(f"ending {self.node.get('id')} {self.node.get(INKSCAPE_LABEL)}")
        return stitch_groups

    def fatal(self, message):
        label = self.node.get(INKSCAPE_LABEL)
        id = self.node.get("id")
        if label:
            name = "%s (%s)" % (label, id)
        else:
            name = id

        # L10N used when showing an error message to the user such as
        # "Some Path (path1234): error: satin column: One or more of the rungs doesn't intersect both rails."
        error_msg = "%s: %s %s" % (name, _("error:"), message)
        inkex.errormsg(error_msg)
        sys.exit(1)

    def validation_errors(self):
        """Return a list of errors with this Element.

        Validation errors will prevent the Element from being stitched.

        Return value: an iterable or generator of instances of subclasses of ValidationError
        """
        return []

    def validation_warnings(self):
        """Return a list of warnings about this Element.

        Validation warnings don't prevent the Element from being stitched but
        the user should probably fix them anyway.

        Return value: an iterable or generator of instances of subclasses of ValidationWarning
        """
        return []

    def is_valid(self):
        # We have to iterate since it could be a generator.
        for error in self.validation_errors():
            return False

        return True

    def validate(self):
        """Print an error message and exit if this Element is invalid."""

        for error in self.validation_errors():
            # note that self.fatal() exits, so this only shows the first error
            self.fatal(error.description)