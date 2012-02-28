# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model import PropertyType
import code
import cpp_util
import util_cc_helper

class CCGenerator(object):
  """A .cc generator for a namespace.
  """
  def __init__(self, namespace, cpp_type_generator):
    self._cpp_type_generator = cpp_type_generator
    self._namespace = namespace
    self._target_namespace = (
        self._cpp_type_generator.GetCppNamespaceName(self._namespace))
    self._util_cc_helper = (
        util_cc_helper.UtilCCHelper(self._cpp_type_generator))

  def Generate(self):
    """Generates a code.Code object with the .cc for a single namespace.
    """
    c = code.Code()
    (c.Append(cpp_util.CHROMIUM_LICENSE)
      .Append()
      .Append(cpp_util.GENERATED_FILE_MESSAGE % self._namespace.source_file)
      .Append()
      .Append(self._util_cc_helper.GetIncludePath())
      .Append('#include "%s/%s.h"' %
          (self._namespace.source_file_dir, self._namespace.name))
    )
    includes = self._cpp_type_generator.GenerateIncludes()
    if not includes.IsEmpty():
      (c.Concat(includes)
        .Append()
      )

    (c.Append()
      .Append('using base::Value;')
      .Append('using base::DictionaryValue;')
      .Append('using base::ListValue;')
      .Append()
      .Concat(self._cpp_type_generator.GetRootNamespaceStart())
      .Concat(self._cpp_type_generator.GetNamespaceStart())
      .Append()
    )
    if self._namespace.types:
      (c.Append('//')
        .Append('// Types')
        .Append('//')
        .Append()
      )
    for type_ in self._namespace.types.values():
      (c.Concat(self._GenerateType(type_.name, type_))
        .Append()
      )
    if self._namespace.functions:
      (c.Append('//')
        .Append('// Functions')
        .Append('//')
        .Append()
      )
    for function in self._namespace.functions.values():
      (c.Concat(self._GenerateFunction(function))
        .Append()
      )
    (c.Concat(self._cpp_type_generator.GetNamespaceEnd())
      .Concat(self._cpp_type_generator.GetRootNamespaceEnd())
      .Append()
    )
    # TODO(calamity): Events
    return c

  def _GenerateType(self, cpp_namespace, type_):
    """Generates the function definitions for a type.
    """
    classname = cpp_util.Classname(type_.name)
    c = code.Code()

    (c.Concat(self._GeneratePropertyFunctions(
        cpp_namespace, type_.properties.values()))
      .Append('%(namespace)s::%(classname)s() {}')
      .Append('%(namespace)s::~%(classname)s() {}')
      .Append()
    )
    if type_.from_json:
      (c.Concat(self._GenerateTypePopulate(cpp_namespace, type_))
        .Append()
      )
    if type_.from_client:
      c.Concat(self._GenerateTypeToValue(cpp_namespace, type_))
    c.Append()
    c.Substitute({'classname': classname, 'namespace': cpp_namespace})

    return c

  def _GenerateTypePopulate(self, cpp_namespace, type_):
    """Generates the function for populating a type given a pointer to it.
    """
    classname = cpp_util.Classname(type_.name)
    c = code.Code()
    (c.Append('// static')
      .Sblock('bool %(namespace)s::Populate'
              '(const Value& value, %(name)s* out) {')
        .Append('if (!value.IsType(Value::TYPE_DICTIONARY))')
        .Append('  return false;')
        .Append('const DictionaryValue* dict = '
                'static_cast<const DictionaryValue*>(&value);')
        .Append()
    )
    for prop in type_.properties.values():
      c.Concat(self._InitializePropertyToDefault(prop, 'out'))
    for prop in type_.properties.values():
      c.Concat(self._GenerateTypePopulateProperty(prop, 'dict', 'out'))
    (c.Append('return true;')
      .Eblock('}')
    )
    c.Substitute({'namespace': cpp_namespace, 'name': classname})
    return c

  def _GenerateTypePopulateProperty(self, prop, src, dst):
    """Generate the code to populate a single property in a type.

    src: DictionaryValue*
    dst: Type*
    """
    c = code.Code()
    value_var = prop.unix_name + '_value'
    c.Append('Value* %(value_var)s = NULL;')
    if prop.optional:
      (c.Sblock(
          'if (%(src)s->GetWithoutPathExpansion("%(key)s", &%(value_var)s)) {'
        )
        .Concat(self._GeneratePopulatePropertyFromValue(
            prop, value_var, dst, 'false'))
        .Eblock('}')
      )
    else:
      (c.Append(
          'if (!%(src)s->GetWithoutPathExpansion("%(key)s", &%(value_var)s))')
        .Append('  return false;')
        .Concat(self._GeneratePopulatePropertyFromValue(
            prop, value_var, dst, 'false'))
      )
    c.Append()
    c.Substitute({'value_var': value_var, 'key': prop.name, 'src': src})
    return c

  def _GenerateTypeToValue(self, cpp_namespace, type_):
    """Generates a function that serializes the type into a |DictionaryValue|.
    """
    c = code.Code()
    (c.Sblock('scoped_ptr<DictionaryValue> %s::ToValue() const {' %
          cpp_namespace)
        .Append('scoped_ptr<DictionaryValue> value(new DictionaryValue());')
        .Append()
    )
    for prop in type_.properties.values():
      if prop.optional:
        if prop.type_ == PropertyType.ENUM:
          c.Sblock('if (%s != %s)' %
              (prop.unix_name, self._cpp_type_generator.GetEnumNoneValue(prop)))
        else:
          c.Sblock('if (%s.get())' % prop.unix_name)
      c.Append('value->SetWithoutPathExpansion("%s", %s);' % (
          prop.name,
          self._CreateValueFromProperty(prop, prop.unix_name)))
      if prop.optional:
        c.Eblock();
    (c.Append()
      .Append('return value.Pass();')
      .Eblock('}')
    )
    return c

  def _GenerateFunction(self, function):
    """Generates the definitions for function structs.
    """
    classname = cpp_util.Classname(function.name)
    c = code.Code()

    # Params::Populate function
    if function.params:
      c.Concat(self._GeneratePropertyFunctions(classname + '::Params',
          function.params))
      (c.Append('%(name)s::Params::Params() {}')
        .Append('%(name)s::Params::~Params() {}')
        .Append()
        .Concat(self._GenerateFunctionParamsCreate(function))
        .Append()
      )

    # Result::Create function
    if function.callback:
      c.Concat(self._GenerateFunctionResultCreate(function))

    c.Substitute({'name': classname})

    return c

  def _GenerateCreateEnumValue(self, cpp_namespace, prop):
    """Generates a function that returns the |StringValue| representation of an
    enum.
    """
    c = code.Code()
    c.Append('// static')
    c.Sblock('scoped_ptr<Value> %(cpp_namespace)s::CreateEnumValue(%(arg)s) {')
    c.Sblock('switch (%s) {' % prop.unix_name)
    if prop.optional:
      (c.Append('case %s: {' % self._cpp_type_generator.GetEnumNoneValue(prop))
        .Append('  return scoped_ptr<Value>();')
        .Append('}')
      )
    for enum_value in prop.enum_values:
      (c.Append('case %s: {' %
          self._cpp_type_generator.GetEnumValue(prop, enum_value))
        .Append('  return scoped_ptr<Value>(Value::CreateStringValue("%s"));' %
            enum_value)
        .Append('}')
      )
    (c.Append('default: {')
      .Append('  return scoped_ptr<Value>();')
      .Append('}')
    )
    c.Eblock('}')
    c.Eblock('}')
    c.Substitute({
        'cpp_namespace': cpp_namespace,
        'arg': cpp_util.GetParameterDeclaration(
            prop, self._cpp_type_generator.GetType(prop))
    })
    return c

  def _CreateValueFromProperty(self, prop, var):
    """Creates a Value given a single property. Generated code passes ownership
    to caller.

    var: variable or variable*
    """
    if prop.type_ == PropertyType.CHOICES:
      # CHOICES conversion not implemented because it's not used. If needed,
      # write something to generate a function that returns a scoped_ptr<Value>
      # and put it in _GeneratePropertyFunctions.
      raise NotImplementedError(
          'Conversion of CHOICES to Value not implemented')
    if prop.type_ in (PropertyType.REF, PropertyType.OBJECT):
      if prop.optional:
        return '%s->ToValue().release()' % var
      else:
        return '%s.ToValue().release()' % var
    elif prop.type_ == PropertyType.ENUM:
      return 'CreateEnumValue(%s).release()' % var
    elif prop.type_ == PropertyType.ARRAY:
      return '%s.release()' % self._util_cc_helper.CreateValueFromArray(
          prop, var)
    elif prop.type_.is_fundamental:
      if prop.optional:
        var = '*' + var
      return {
          PropertyType.STRING: 'Value::CreateStringValue(%s)',
          PropertyType.BOOLEAN: 'Value::CreateBooleanValue(%s)',
          PropertyType.INTEGER: 'Value::CreateIntegerValue(%s)',
          PropertyType.DOUBLE: 'Value::CreateDoubleValue(%s)',
      }[prop.type_] % var
    else:
      raise NotImplementedError('Conversion of %s to Value not '
          'implemented' % repr(prop.type_))

  def _GenerateParamsCheck(self, function, var):
    """Generates a check for the correct number of arguments when creating
    Params.
    """
    c = code.Code()
    num_required = 0
    for param in function.params:
      if not param.optional:
        num_required += 1
    if num_required == len(function.params):
      c.Append('if (%(var)s.GetSize() != %(total)d)')
    elif not num_required:
      c.Append('if (%(var)s.GetSize() > %(total)d)')
    else:
      c.Append('if (%(var)s.GetSize() < %(required)d'
          ' || %(var)s.GetSize() > %(total)d)')
    c.Append('  return scoped_ptr<Params>();')
    c.Substitute({
        'var': var,
        'required': num_required,
        'total': len(function.params),
    })
    return c

  def _GenerateFunctionParamsCreate(self, function):
    """Generate function to create an instance of Params. The generated
    function takes a ListValue of arguments.
    """
    classname = cpp_util.Classname(function.name)
    c = code.Code()
    (c.Append('// static')
      .Sblock('scoped_ptr<%(classname)s::Params> %(classname)s::Params::Create'
               '(const ListValue& args) {')
      .Concat(self._GenerateParamsCheck(function, 'args'))
      .Append('scoped_ptr<Params> params(new Params());')
    )
    c.Substitute({'classname': classname})

    for param in function.params:
      c.Concat(self._InitializePropertyToDefault(param, 'params'))

    for i, param in enumerate(function.params):
      # Any failure will cause this function to return. If any argument is
      # incorrect or missing, those following it are not processed. Note that
      # this is still correct in the case of multiple optional arguments as an
      # optional argument at position 4 cannot exist without an argument at
      # position 3.
      failure_value = 'scoped_ptr<Params>()'
      if param.optional:
        arg_missing_value = 'params.Pass()'
      else:
        arg_missing_value = failure_value
      c.Append()
      value_var = param.unix_name + '_value'
      (c.Append('Value* %(value_var)s = NULL;')
        .Append('if (!args.Get(%(i)s, &%(value_var)s) || '
            '%(value_var)s->IsType(Value::TYPE_NULL))')
        .Append('  return %s;' % arg_missing_value)
        .Concat(self._GeneratePopulatePropertyFromValue(
            param, value_var, 'params', failure_value))
      )
      c.Substitute({'value_var': value_var, 'i': i})
    (c.Append()
      .Append('return params.Pass();')
      .Eblock('}')
      .Append()
    )

    return c

  def _GeneratePopulatePropertyFromValue(
      self, prop, value_var, dst, failure_value, check_type=True):
    """Generates code to populate a model.Property given a Value*. The
    existence of data inside the Value* is assumed so checks for existence
    should be performed before the code this generates.

    prop: the property the code is populating.
    value_var: a Value* that should represent |prop|.
    dst: the object with |prop| as a member.
    failure_value: the value to return if |prop| cannot be extracted from
    |value_var|
    check_type: if true, will check if |value_var| is the correct Value::Type
    """
    c = code.Code()
    c.Sblock('{')

    if check_type and prop.type_ != PropertyType.CHOICES:
      (c.Append('if (!%(value_var)s->IsType(%(value_type)s))')
        .Append('  return %(failure_value)s;')
      )

    if prop.type_.is_fundamental:
      if prop.optional:
        (c.Append('%(ctype)s temp;')
          .Append('if (%s)' %
              cpp_util.GetAsFundamentalValue(prop, value_var, '&temp'))
          .Append('  %(dst)s->%(name)s.reset(new %(ctype)s(temp));')
        )
      else:
        (c.Append('if (!%s)' %
            cpp_util.GetAsFundamentalValue(
                prop, value_var, '&%s->%s' % (dst, prop.unix_name)))
          .Append('return %(failure_value)s;')
        )
    elif prop.type_ in (PropertyType.OBJECT, PropertyType.REF):
      if prop.optional:
        (c.Append('DictionaryValue* dictionary = NULL;')
          .Append('if (!%(value_var)s->GetAsDictionary(&dictionary))')
          .Append('  return %(failure_value)s;')
          .Append('scoped_ptr<%(ctype)s> temp(new %(ctype)s());')
          .Append('if (!%(ctype)s::Populate(*dictionary, temp.get()))')
          .Append('  return %(failure_value)s;')
          .Append('%(dst)s->%(name)s = temp.Pass();')
        )
      else:
        (c.Append('DictionaryValue* dictionary = NULL;')
          .Append('if (!%(value_var)s->GetAsDictionary(&dictionary))')
          .Append('  return %(failure_value)s;')
          .Append(
              'if (!%(ctype)s::Populate(*dictionary, &%(dst)s->%(name)s))')
          .Append('  return %(failure_value)s;')
        )
    elif prop.type_ == PropertyType.ARRAY:
      # util_cc_helper deals with optional and required arrays
      (c.Append('ListValue* list = NULL;')
        .Append('if (!%(value_var)s->GetAsList(&list))')
        .Append('  return %(failure_value)s;')
        .Append('if (!%s)' % self._util_cc_helper.PopulateArrayFromList(
            prop, 'list', dst + '->' + prop.unix_name))
        .Append('  return %(failure_value)s;')
      )
    elif prop.type_ == PropertyType.CHOICES:
      type_var = '%(dst)s->%(name)s_type'
      c.Sblock('switch (%(value_var)s->GetType()) {')
      for choice in self._cpp_type_generator.GetExpandedChoicesInParams([prop]):
        (c.Sblock('case %s: {' % cpp_util.GetValueType(choice))
            .Concat(self._GeneratePopulatePropertyFromValue(
                choice, value_var, dst, failure_value, check_type=False))
            .Append('%s = %s;' %
                (type_var,
                 self._cpp_type_generator.GetEnumValue(
                     prop, choice.type_.name)))
            .Append('break;')
          .Eblock('}')
        )
      (c.Append('default:')
        .Append('  return %(failure_value)s;')
      )
      c.Eblock('}')
    elif prop.type_ == PropertyType.ENUM:
      (c.Append('std::string enum_temp;')
        .Append('if (!%(value_var)s->GetAsString(&enum_temp))')
        .Append('  return %(failure_value)s;')
      )
      for i, enum_value in enumerate(prop.enum_values):
        (c.Append(
            ('if' if i == 0 else 'else if') +
            '(enum_temp == "%s")' % enum_value)
          .Append('  %s->%s = %s;' % (
            dst,
            prop.unix_name,
            self._cpp_type_generator.GetEnumValue(prop, enum_value)))
        )
      (c.Append('else')
        .Append('  return %(failure_value)s;')
      )
    else:
      raise NotImplementedError(prop.type_)
    c.Eblock('}')
    sub = {
        'value_var': value_var,
        'name': prop.unix_name,
        'dst': dst,
        'failure_value': failure_value,
    }
    if prop.type_ != PropertyType.CHOICES:
      sub['ctype'] = self._cpp_type_generator.GetType(prop)
      sub['value_type'] = cpp_util.GetValueType(prop)
    c.Substitute(sub)
    return c

  def _GeneratePropertyFunctions(self, param_namespace, params):
    """Generate the functions for structures generated by a property such as
    CreateEnumValue for ENUMs and Populate/ToValue for Params/Result objects.
    """
    c = code.Code()
    for param in params:
      if param.type_ == PropertyType.OBJECT:
        c.Concat(self._GenerateType(
            param_namespace + '::' + cpp_util.Classname(param.name),
            param))
        c.Append()
      elif param.type_ == PropertyType.ENUM:
        c.Concat(self._GenerateCreateEnumValue(param_namespace, param))
        c.Append()
    return c

  def _GenerateFunctionResultCreate(self, function):
    """Generate function to create a Result given the return value.
    """
    classname = cpp_util.Classname(function.name)
    c = code.Code()
    params = function.callback.params

    if not params:
      (c.Append('Value* %s::Result::Create() {' % classname)
        .Append('  return Value::CreateNullValue();')
        .Append('}')
      )
    else:
      expanded_params = self._cpp_type_generator.GetExpandedChoicesInParams(
          params)
      c.Concat(self._GeneratePropertyFunctions(
          classname + '::Result', expanded_params))

      # If there is a single parameter, this is straightforward. However, if
      # the callback parameter is of 'choices', this generates a Create method
      # for each choice. This works because only 1 choice can be returned at a
      # time.
      for param in expanded_params:
        # We treat this argument as 'required' to avoid wrapping it in a
        # scoped_ptr if it's optional.
        param_copy = param.Copy()
        param_copy.optional = False
        c.Sblock('Value* %(classname)s::Result::Create(const %(arg)s) {')
        c.Append('return %s;' %
           self._CreateValueFromProperty(param_copy, param_copy.unix_name))
        c.Eblock('}')
        c.Substitute({'classname': classname,
            'arg': cpp_util.GetParameterDeclaration(
                param_copy, self._cpp_type_generator.GetType(param_copy))
        })

    return c

  def _InitializePropertyToDefault(self, prop, dst):
    """Initialize a model.Property to its default value inside an object.

    dst: Type*
    """
    c = code.Code()
    if prop.type_ in (PropertyType.ENUM, PropertyType.CHOICES):
      if prop.optional:
        prop_name = prop.unix_name
        if prop.type_ == PropertyType.CHOICES:
          prop_name = prop.unix_name + '_type'
        c.Append('%s->%s = %s;' % (
          dst,
          prop_name,
          self._cpp_type_generator.GetEnumNoneValue(prop)))
    return c

