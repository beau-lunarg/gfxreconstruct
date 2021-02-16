#!/usr/bin/env python3
#
# Copyright (c) 2021 LunarG, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import sys
from base_generator\
    import BaseGenerator, BaseGeneratorOptions, ValueInfo, write


class Dx12GeneratorOptions(BaseGeneratorOptions):
    """Options for generating C++ function declarations for Dx12 API."""

    def __init__(self, blacklists=None, platform_types=None, filename=None,
                 directory='.', prefix_text='', protect_file=False,
                 protect_feature=True):
        BaseGeneratorOptions.__init__(
            self,
            blacklists,
            platform_types,
            filename,
            directory,
            prefix_text,
            protect_file,
            protect_feature)


class Dx12BaseGenerator(BaseGenerator):

    ARRAY_SIZE_LIST = [
        ['D3D12_PIPELINE_STATE_STREAM_DESC',
            'pPipelineStateSubobjectStream', 'SizeInBytes'],
        ['D3D12_AUTO_BREADCRUMB_NODE',
            'pCommandHistory', 'BreadcrumbCount'],
        ['D3D12_AUTO_BREADCRUMB_NODE1',
            'pCommandHistory', 'BreadcrumbCount'],
        ['D3D12_AUTO_BREADCRUMB_NODE1',
            'pBreadcrumbContexts', 'BreadcrumbContextsCount'],
        ['D3D12_FEATURE_DATA_PROTECTED_RESOURCE_SESSION_TYPES',
            'pTypes', 'Count'],
    ]

    # convert struct, class, or union type into the parsed type or convert
    # some define into plain type. The third value is pointer level.
    # If the new type is not a pointer, the value is 0. * is 1. ** is 2.
    # The Fourth value is if it's const.
    CONVERT_DEFINE_LIST = [
        [['D3D12_RECT', 'RECT'], 'tagRECT', 0, False],
        [['POINT'], 'tagPOINT', 0, False],
        [['REFIID', 'REFGUID', 'IID'], 'GUID', 0, False],
        [['DXGI_RGBA'], 'D3DCOLORVALUE', 0, False],
        [['ID3DBlob'], 'ID3D10Blob', 0, False],
        [['SECURITY_ATTRIBUTES'], '_SECURITY_ATTRIBUTES', 0, False],
        [['D3D12_PRIMITIVE_TOPOLOGY'], 'D3D_PRIMITIVE_TOPOLOGY', 0, False],
        [['LPCVOID'], 'void', 1, True],
        [['LPVOID'], 'void', 1, False],
        [['WCHAR'], 'wchar_t', 0, False],
        [['LPCSTR'], 'char', 1, True],
        [['LPCWSTR'], 'wchar_t', 1, True],
    ]

    # convert base type into the encode function name
    CONVERT_FUNCTION_LIST = [
        [['BYTE', 'byte', 'UINT8', 'unsigned char'], 'UInt8'],
        [['INT8'], 'Int8'],
        [['UINT16', 'unsigned short'], 'UInt16'],
        [['SHORT'], 'Int16'],
        [['unsigned long', 'ULONG', 'DWORD', 'UINT', 'UINT32',
            'unsigned int', 'DXGI_USAGE'], 'UInt32'],
        [['HRESULT', 'LONG', 'BOOL', 'INT', 'int'], 'Int32'],
        [['UINT64', 'D3D12_GPU_VIRTUAL_ADDRESS', 'SIZE_T'], 'UInt64'],
        [['LONG_PTR'], 'Int64'],
        [['FLOAT', 'float'], 'Float'],
        [['HANDLE', 'HMONITOR', 'HWND', 'HMODULE', 'HDC'], 'Handle'],
        [['void'], 'Void'],
        [['char'], 'String'],
        [['wchar_t'], 'WString'],
        [['PFN_DESTRUCTION_CALLBACK'], 'Function'],
    ]

    BIT_FIELD_LIST = [
        ['D3D12_RAYTRACING_INSTANCE_DESC',
            'InstanceID', ':24'],
        ['D3D12_RAYTRACING_INSTANCE_DESC',
            'InstanceMask', ':8'],
        ['D3D12_RAYTRACING_INSTANCE_DESC',
            'InstanceContributionToHitGroupIndex', ':24'],
        ['D3D12_RAYTRACING_INSTANCE_DESC',
            'Flags', ':8'],
    ]

    # Some functions annotate COM pointer parameters that have a void**
    # with the '_Out_' token instead of '_COM_Outptr_'.  This table
    # contains the COM pointer parameters that are not annotated as
    # COM pointers.
    COM_POINTER_PARAMS = {
        'D3D12CreateRootSignatureDeserializer' :
           ['ppRootSignatureDeserializer'],
        'D3D12CreateVersionedRootSignatureDeserializer' :
           ['ppRootSignatureDeserializer'] }

    def __init__(self, source_dict, dx12_prefix_strings,
                 err_file=sys.stderr, warn_file=sys.stderr, diag_file=sys.stdout):
        BaseGenerator.__init__(
            self,
            process_cmds=True,
            process_structs=True,
            feature_break=True,
            err_file=err_file,
            warn_file=warn_file,
            diag_file=diag_file)
        self.source_dict = source_dict
        self.dx12_prefix_strings = dx12_prefix_strings
        self.feature_method_params = dict()
        self.check_blacklist = False

    def clean_type_define(self, type):
        rtn = ''
        types = type.split(" ")
        skip = 0

        for t in types:
            if t[0] == '(':
                skip += 1
                continue
            elif t[0] == ')':
                skip -= 1
                continue
            elif skip:
                continue
            elif t == '_SECURITY_ATTRIBUTES'\
                    or (t[0] != '_' and t != 'STDMETHODCALLTYPE'
                        and t != 'WINAPI' and t != 'IN' and t != 'OUT'):
                if rtn:
                    rtn += ' '
                rtn += t
        return rtn

    def get_return_value_info(self, param_name, param_type):
        pointer = 0
        const = False
        base_type = ''

        const = False
        pointer = 0  # 1: *, 2: ** ...
        types1 = self.clean_type_define(param_type)
        types = types1.split(" ")

        for t in types:
            if t == 'const':
                const = True
            elif t == '*':
                pointer += 1
            elif t != 'struct':
                if base_type:
                    base_type += ' '
                base_type += t

        for e in self.CONVERT_DEFINE_LIST:
            for k in e[0]:
                if base_type == k:
                    if e[3]:
                        const = True
                    base_type = e[1]
                    pointer += e[2]

        return ValueInfo(
            name=param_name,
            base_type=base_type,
            full_type=param_type,
            pointer_count=pointer,
            is_const=const)

    def get_value_info(self, param):
        struct_name = ''
        if 'parent' in param and 'name' in param['parent']:
            struct_name = param['parent']['name']

        name = param['name']
        full_type = param['type']
        const = False
        pointer = 0  # 1: *, 2: ** ...
        types1 = self.clean_type_define(full_type)
        types = types1.split(" ")
        base_type = ''

        for t in types:
            if t == 'const':
                const = True
            elif t == '*':
                pointer += 1
            elif t != 'struct':
                if base_type:
                    base_type += ' '
                base_type += t

        for e in self.CONVERT_DEFINE_LIST:
            for k in e[0]:
                if base_type == k:
                    if e[3]:
                        const = True
                    base_type = e[1]
                    pointer += e[2]

        union = self.get_union(base_type)
        union_members = list()
        if union:
            for m in union['members']:
                union_members.append([m['name'], m['type']])

        array_length = None
        array_capacity = 0
        array_dimension = 0
        if 'array_size' in param:
            array_capacity = param['array_size']
            array_length = array_capacity
            if 'multi_dimensional_array' in param:
                array_dimension = param['multi_dimensional_array']

        # Check if it is an array pointer, and get the size of parameter's name.
        if pointer > 0:
            for e in self.ARRAY_SIZE_LIST:
                if e[0] == struct_name and name == e[1]:
                    array_length = e[2]

            if not array_length:
                index_parentheses1 = full_type.find('(')
                if index_parentheses1 != -1:
                    index_parentheses2 = full_type[index_parentheses1 +
                                                   1:
                                                   ].find(')') +\
                                                   index_parentheses1
                    index_parentheses11 = index_parentheses1
                    parentheses = 0

                    while True:
                        index_parentheses111 = full_type[index_parentheses11 +
                                                         1:index_parentheses2
                                                         ].find('(')
                        if index_parentheses111 == -1:
                            break
                        index_parentheses11 += index_parentheses111 + 1
                        parentheses += 1

                    while parentheses > -1:
                        index_parentheses22 = full_type[index_parentheses2 + 1:
                                                        ].find(')')
                        if index_parentheses22 == -1:
                            break
                        index_parentheses2 += index_parentheses22 + 1
                        parentheses -= 1

                    param = full_type[index_parentheses1 +
                                      2:index_parentheses2]
                    if param[0] != '_':
                        param_list = param.split(', ')
                        array_length = param_list[0]
                        if array_length.find('Size') != - \
                                1 and base_type.find('void') == -1:
                            array_length += ('/sizeof ' + base_type)

        return ValueInfo(
            name=name,
            base_type=base_type,
            full_type=full_type,
            pointer_count=pointer,
            array_length=array_length,
            array_capacity=array_capacity,
            array_dimension=array_dimension,
            bitfield_width=self.get_bit_field(struct_name, name),
            is_const=const, union_members=union_members,
            is_com_outptr=self.is_com_outptr(struct_name, name, full_type))

    def gen_type(self, typeinfo, name, alias):
        """Methond override."""
        self.gen_struct(None, None, None)
        self.gen_cmd(None, None, None)
        self.gen_method()
        self.gen_handle()

    def gen_struct(self, typeinfo, typename, alias):
        """Methond override."""
        header_dict = self.source_dict['header_dict']
        for k, v in header_dict.items():
            for k2, v2 in v.classes.items():
                if self.is_required_struct_data(k2, v2):
                    self.feature_struct_members[k2] = self.make_value_info(
                        v2['properties']['public'])

    def gen_cmd(self, cmdinfo, name, alias):
        """Methond override."""
        header_dict = self.source_dict['header_dict']
        for k, v in header_dict.items():
            for m in v.functions:
                if self.is_required_function_data(m):
                    name = m['name']
                    self.feature_cmd_params[name] = (
                        self.clean_type_define(
                            m['rtnType']), '', self.make_value_info(
                            m['parameters']))

    def gen_handle(self):
        # Member override
        self.handle_names = ['HANDLE', 'HMONITOR', 'HWND', 'HMODULE', 'HDC']

    def gen_method(self):
        header_dict = self.source_dict['header_dict']
        for k, v in header_dict.items():
            for k, v in v.classes.items():
                if self.is_required_class_data(v):
                    for m in v['methods']['public']:
                        name = k + '_' + m['name']
                        self.feature_method_params[name] = (
                            self.clean_type_define(
                                m['rtnType']), '', self.make_value_info(
                                m['parameters']))

    def get_filtered_method_names(self):
        return [key for key in self.feature_method_params]

    def make_value_info(self, params):
        """Methond override."""
        values = []
        for p in params:
            values.append(self.get_value_info(p))
        return values

    def get_filtered_struct_names(self):
        """Methond override."""
        if self.check_blacklist:
            return [key for key in self.source_dict['struct_list'] if not self.is_struct_black_listed(key)]
        else:
            return self.source_dict['struct_list']

    def is_struct(self, type):
        """Methond override."""
        # This type is from winnt.h. It isn't parsed. It's in custom classes.
        if type == 'LARGE_INTEGER':
            return True
        struct_list = self.source_dict['struct_list']
        if type in struct_list:
            return True
        return False

    def is_class(self, value):
        """Methond override. Use value, not type because it needs to check void** case."""
        if value.base_type == 'void' and value.pointer_count == 2 and value.is_com_outptr:
            return True

        class_list = self.source_dict['class_list']
        if value.base_type in class_list:
            return True
        return False

    def get_bit_field(self, struct_name, param_name):
        for m in self.BIT_FIELD_LIST:
            if m[0] == struct_name and m[1] == param_name:
                return m[2]
        return ''

    def is_enum(self, type):
        """Methond override."""
        enum_set = self.source_dict['enum_set']
        if type in enum_set:
            return True
        return False

    def get_union(self, type):
        if type[:12] == '<anon-union-':
            union_dict = self.source_dict['union_dict']
            return union_dict.get(type)
        return None

    def convert_function(self, type):
        for e in self.CONVERT_FUNCTION_LIST:
            for k in e[0]:
                if type == k:
                    return e[1]
        return type

    def make_invocation_type_name(self, base_type):
        """Methond override."""
        type = self.convert_function(base_type)
        type = BaseGenerator.make_invocation_type_name(self, type)
        if type == 'Function':
            type = 'FunctionPtr'
        else:
            union = self.get_union(type)
            if union:
                type = 'Union'
        return type

    def is_required_function_data(self, function_source_data):
        name = function_source_data['name']
        if function_source_data['parent'] is None\
           and name[:7] != 'DEFINE_'\
           and name[:8] != 'DECLARE_'\
           and name != 'InlineIsEqualGUID'\
           and name != 'IsEqualGUID'\
           and name[:8] != 'operator':
            return True
        return False

    def is_required_class_data(self, class_source_data):
        if class_source_data['declaration_method'] == 'class':
            return True
        return False

    def is_required_struct_data(self, struct_type, struct_source_data):
        if struct_source_data['declaration_method'] == 'struct'\
           and (not self.check_blacklist or not struct_source_data['name'] in self.STRUCT_BLACKLIST)\
           and struct_type[-4:] != 'Vtbl'\
           and struct_type.find("::<anon-union-") == -1:
            return True
        return False

    def is_com_outptr(self, func_name, param_name, param_full_type):
        if 'COM_Outptr' in param_full_type:
            return True
        elif (func_name in self.COM_POINTER_PARAMS and
              param_name in self.COM_POINTER_PARAMS[func_name]):
            return True
        return False
