# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Generator that produces an externs file for the Closure Compiler.
Note: This is a work in progress, and generated externs may require tweaking.

See https://developers.google.com/closure/compiler/docs/api-tutorial3#externs
"""

from code import Code
from model import *
from schema_util import *

import os
from datetime import datetime

LICENSE = ("""// Copyright %s The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
""" % datetime.now().year)

class JsExternsGenerator(object):
  def Generate(self, namespace):
    return _Generator(namespace).Generate()

class _Generator(object):
  def __init__(self, namespace):
    self._namespace = namespace

  def Generate(self):
    """Generates a Code object with the schema for the entire namespace.
    """
    c = Code()
    (c.Append(LICENSE)
        .Append()
        .Append('/** @fileoverview Externs generated from namespace: %s */' %
                self._namespace.name)
        .Append())

    c.Cblock(self._GenerateNamespaceObject())

    for js_type in self._namespace.types.values():
      c.Cblock(self._GenerateType(js_type))

    for function in self._namespace.functions.values():
      c.Cblock(self._GenerateFunction(function))

    for event in self._namespace.events.values():
      c.Cblock(self._GenerateEvent(event))

    return c

  def _GenerateType(self, js_type):
    """Given a Type object, returns the Code for this type's definition.
    """
    c = Code()
    if js_type.property_type is PropertyType.ENUM:
      c.Concat(self._GenerateEnumJsDoc(js_type))
    else:
      c.Concat(self._GenerateTypeJsDoc(js_type))

    return c

  def _GenerateEnumJsDoc(self, js_type):
    """ Given an Enum Type object, returns the Code for the enum's definition.
    """
    c = Code()
    c.Append('/**').Append(' * @enum {string}').Append(' */')
    c.Append('chrome.%s.%s = {' % (self._namespace.name, js_type.name))
    c.Append('\n'.join(
        ["  %s: '%s'," % (v.name, v.name) for v in js_type.enum_values]))
    c.Append('};')
    return c

  def _IsTypeConstructor(self, js_type):
    """Returns true if the given type should be a @constructor. If this returns
       false, the type is a typedef.
    """
    return any(prop.type_.property_type is PropertyType.FUNCTION
               for prop in js_type.properties.values())

  def _GenerateTypeJsDoc(self, js_type):
    """Generates the documentation for a type as a Code.

    Returns an empty code object if the object has no documentation.
    """
    c = Code()
    c.Append('/**')

    if js_type.description:
      for line in js_type.description.splitlines():
        c.Comment(line, comment_prefix = ' * ')

    is_constructor = self._IsTypeConstructor(js_type)
    if is_constructor:
      c.Comment('@constructor', comment_prefix = ' * ')
    else:
      c.Concat(self._GenerateTypedef(js_type.properties))

    c.Append(' */')

    var = 'var ' + js_type.simple_name
    if is_constructor: var += ' = function() {}'
    var += ';'
    c.Append(var)

    return c

  def _GenerateTypedef(self, properties):
    """Given an OrderedDict of properties, returns a Code containing a @typedef.
    """
    if not properties: return Code()

    lines = []
    lines.append('@typedef {{')
    for field, prop in properties.items():
      js_type = self._TypeToJsType(prop.type_)
      if prop.optional:
        js_type = '(%s|undefined)' % js_type
      lines.append('  %s: %s,' % (field, js_type))

    # Remove last trailing comma.
    # TODO(devlin): This will be unneeded, if when
    # https://github.com/google/closure-compiler/issues/796 is fixed.
    lines[-1] = lines[-1][:-1]
    lines.append('}}')
    # TODO(tbreisacher): Add '@see <link to documentation>'.

    c = Code()
    c.Append('\n'.join([' * ' + line for line in lines]))
    return c

  def _GenerateFunctionJsDoc(self, function):
    """Generates the documentation for a function as a Code.

    Returns an empty code object if the object has no documentation.
    """
    c = Code()
    c.Append('/**')

    if function.description:
      for line in function.description.split('\n'):
        c.Comment(line, comment_prefix=' * ')

    for param in function.params:
      js_type = self._TypeToJsType(param.type_)

      if param.optional:
        js_type += '='

      param_doc = '@param {%s} %s %s' % (js_type,
                                         param.name,
                                         param.description or '')
      c.Comment(param_doc, comment_prefix=' * ')

    if function.callback:
      # TODO(tbreisacher): Convert Function to function() for better
      # typechecking.
      js_type = 'Function'
      if function.callback.optional:
        js_type += '='
      param_doc = '@param {%s} %s %s' % (js_type,
                                         function.callback.name,
                                         function.callback.description or '')
      c.Comment(param_doc, comment_prefix=' * ')

    if function.returns:
      return_doc = '@return {%s} %s' % (self._TypeToJsType(function.returns),
                                        function.returns.description)
      c.Comment(return_doc, comment_prefix=' * ')

    c.Append(' */')
    return c

  def _TypeToJsType(self, js_type):
    """Converts a model.Type to a JS type (number, Array, etc.)"""
    if js_type.property_type in (PropertyType.INTEGER, PropertyType.DOUBLE):
      return 'number'
    elif js_type.property_type is PropertyType.OBJECT:
      return 'Object'
    elif js_type.property_type is PropertyType.ARRAY:
      return 'Array'
    elif js_type.property_type is PropertyType.REF:
      ref_type = js_type.ref_type
      # Enums are defined as chrome.fooAPI.MyEnum, but types are defined simply
      # as MyType.
      if self._namespace.types[ref_type].property_type is PropertyType.ENUM:
        ref_type = 'chrome.%s.%s' % (self._namespace.name, ref_type)
      return ref_type
    elif js_type.property_type.is_fundamental:
      return js_type.property_type.name
    else:
      return '?' # TODO(tbreisacher): Make this more specific.

  def _GenerateFunction(self, function):
    """Generates the code representing a function, including its documentation.
       For example:

       /**
        * @param {string} title The new title.
        */
       chrome.window.setTitle = function(title) {};
    """
    c = Code()
    params = self._GenerateFunctionParams(function)
    (c.Concat(self._GenerateFunctionJsDoc(function))
      .Append('chrome.%s.%s = function(%s) {};' % (self._namespace.name,
                                                   function.name,
                                                   params))
    )
    return c

  def _GenerateEvent(self, event):
    """Generates the code representing an event.
       For example:

       /** @type {!ChromeEvent} */
       chrome.bookmarks.onChildrenReordered;
    """
    c = Code()
    (c.Append('/** @type {!ChromeEvent} */')
      .Append('chrome.%s.%s;' % (self._namespace.name, event.name)))
    return c

  def _GenerateNamespaceObject(self):
    """Generates the code creating namespace object.
       For example:

       /**
        * @const
        */
       chrome.bookmarks = {};
    """
    c = Code()
    (c.Append("""/**
 * @const
 */""")
      .Append('chrome.%s = {};' % self._namespace.name))
    return c

  def _GenerateFunctionParams(self, function):
    params = function.params[:]
    if function.callback:
      params.append(function.callback)
    return ', '.join(param.name for param in params)
