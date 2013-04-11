#!/usr/bin/env python

import sys
import clang.cindex
import clang.enumerations

access_specifiers = ["", "public", "protected", "private"]

def verbose(*args, **kwargs):
    '''filter predicate for show_ast: show all'''
    return True
def no_system_includes(cursor, level):
    '''filter predicate for show_ast: filter out verbose stuff from system include files'''
    return (level!= 1) or (cursor.location.file is not None and not cursor.location.file.name.startswith('/usr/include'))
 
# A function show(level, *args) would have been simpler but less fun
# and you'd need a separate parameter for the AST walkers if you want it to be exchangeable.
class Level(int):
    '''represent currently visited level of a tree'''
    def show(self, *args):
        '''pretty print an indented line'''
        print '\t'*self + ' '.join(map(str, args))
    def __add__(self, inc):
        '''increase level'''
        return Level(super(Level, self).__add__(inc))
    def open(self, type, location, **kwargs):
        '''Opens an XML tag'''
        attributes = {
            "file" : location.file,
            "line" : location.line,
            "column" : location.column,
            }
        attributes.update(kwargs)
        print '\t'*self + '<%s %s>' % (type, ' '.join(['%s="%s"' % (key, value) for key, value in attributes.items()]))
    def close(self, type):
        '''Closes an XML tag'''
        print '\t'*self + '</%s>' % type
    def openclose(self, type, **kwargs):
        self.open(type, **kwargs)
        self.close(type)
 
def is_valid_type(t):
    '''used to check if a cursor has a type'''
    return t.kind != clang.cindex.TypeKind.INVALID
    
def qualifiers(t):
    '''set of qualifiers of a type'''
    q = set()
    if t.is_const_qualified(): q.add('const')
    if t.is_volatile_qualified(): q.add('volatile')
    if t.is_restrict_qualified(): q.add('restrict')
    return q
 
def show_type(t, level, title):
    '''pretty print type AST'''
    level.show(title, retrieve_type(t))

def is_definition(cursor):
    ''' Returns true if the cursor is the definition '''
    return (
        (cursor.is_definition() and not cursor.kind in (
            clang.cindex.CursorKind.CXX_ACCESS_SPEC_DECL,
            clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER,
            clang.cindex.CursorKind.UNEXPOSED_DECL,
            )) or
        cursor.kind in (
            clang.cindex.CursorKind.FUNCTION_DECL,
            clang.cindex.CursorKind.CXX_METHOD,
            clang.cindex.CursorKind.FUNCTION_TEMPLATE,
            ))

def is_named_scope(cursor):
    ''' Returns true if the cursor is a name declaration   '''
    return cursor.kind in (
        clang.cindex.CursorKind.NAMESPACE,
        clang.cindex.CursorKind.STRUCT_DECL,
        clang.cindex.CursorKind.UNION_DECL,
        clang.cindex.CursorKind.ENUM_DECL,
        clang.cindex.CursorKind.CLASS_DECL,
        clang.cindex.CursorKind.CLASS_TEMPLATE,
        clang.cindex.CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
        )

def semantic_parents(cursor):
    import collections

    p = collections.deque()
    c = cursor.semantic_parent
    while c and is_named_scope(c):
        p.appendleft(c.displayname)
        c = c.semantic_parent
    return list(p)

def retrieve_type(t):
    '''retrieve actual type'''
    if is_valid_type(t.get_pointee()):
        pointee = ""
        if t.kind == clang.cindex.TypeKind.POINTER:
            pointee = "*"
        if t.kind == clang.cindex.TypeKind.LVALUEREFERENCE:
            pointee = "&"
        if t.kind == clang.cindex.TypeKind.RVALUEREFERENCE:
            pointee = "&&"
        return retrieve_type(t.get_pointee()) + pointee + ' '.join(qualifiers(t))
    else:
        cursor = t.get_declaration()
        parents = semantic_parents(cursor)
        if cursor.displayname != "":
            return "::".join(parents + [cursor.displayname])
        else:
            return "::".join(parents + [mangle_type(str(t.kind).split(".")[-1])])

authorized_decl = [
    "CXX_ACCESS_SPEC_DECL",
    "CXX_METHOD",
    "CLASS_DECL",
    "CLASS_TEMPLATE_PARTIAL_SPECIALIZATION",
    "CLASS_DECL",
    "ENUM_DECL",
    "FIELD_DECL",
    "FUNCTION_DECL",
    "NAMESPACE",
    "STRUCT_DECL",
    "TRANSLATION_UNIT",
    "UNION_DECL",
    ]

printable_types = {
    "BOOL" : "bool",
    "CHAR" : "char",
    "CHAR_S" : "char",
    "DOUBLE" : "double",
    "FLOAT" : "float",
    "INT" : "int",
    "LONG" : "long",
    "LONGDOUBLE" : "long double",
    "LONGLONG" : "long long",
    "SCHAR" : "char",
    "UINT" : "unsigned int",
    "ULONG" : "unsigned long",
    "USHORT" : "unsigned short",
    "VOID" : "void",
    }

def mangle_type(type):
    return printable_types.get(type, type)

def show_ast(cursor, filter_pred=verbose, level=Level(), inherited_attributes={}):
    '''pretty print cursor AST'''
    if filter_pred(cursor, level):
        type = str(cursor.kind).split(".")[-1]
        level1 = level+1
        if type not in authorized_decl:
            print "discarding cursor type %s" % type
            return
        if type == "CXX_ACCESS_SPEC_DECL":
            config = clang.cindex.Config()
            inherited_attributes["access"] = access_specifiers[config.lib.clang_getCXXAccessSpecifier(cursor)]
            return
        level.open(type, spelling=cursor.spelling, displayname=cursor.displayname, location=cursor.location, **inherited_attributes)
        if is_valid_type(cursor.type):
            level1.openclose("type", displayname=retrieve_type(cursor.type.get_canonical()), location=cursor.location)
        attributes = {}
        if type == "CLASS_DECL":
            attributes["access"] = "private"
        elif type == "STRUCT_DECL":
            attributes["access"] = "public"
        if type == "CXX_METHOD" or type == "FUNCTION_DECL":
            level1.openclose("result", displayname=retrieve_type(cursor.result_type), location=cursor.location)
            for i, arg in enumerate(cursor.get_arguments()):
              level1.openclose("arg%i" %i, displayname=retrieve_type(arg.type), location=arg.location)
        else:
            for c in cursor.get_children():
                show_ast(c, filter_pred, level1, attributes)
        level.close(type)
 
if __name__ == '__main__':
    index = clang.cindex.Index.create()
    tu = index.parse(sys.argv[1], ["-xc++"])
    show_ast(tu.cursor, no_system_includes)
