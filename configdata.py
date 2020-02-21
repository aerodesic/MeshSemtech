#
# A simple data store database with optional backing store.
#
import json
import sys

class ConfigData():
    def __init__(self, read=None, write=None, data=None, version=None):
        self._dirty = False
        self._write = write
        if read != None:
            try:
                self._data = json.loads(read())
                if version != None and self._data['%version'] != version:
                    raise Exception('data version changed')

            except Exception as e:
                sys.print_exception(e)
                self._data = data
                self._data["%version"] = version
                self.flush(force=True)
        else:
            self._data = {}

    # Drill down through a.b.c...z to get data location
    # If 'define' is True, add names as needed to force new symbol to be defined
    def _lookup(self, name, define=False):
        data = self._data
        parts = name.split('.')
        for part in parts[0:-1]:
            if isinstance(data, dict):
                if part in data:
                    data = data[part]
                elif define:
                    data[part] = {}
                    data = data[part]
                    # print("_lookup: added %s to %s" % (part, data))
                else:
                    raise Exception("%s not found" % name)
            else:
                raise Exception("%s not found" % (name))
    
        found = isinstance(data, dict) and (parts[-1] in data or define)
        if found:
            if parts[-1] not in data:
                data[parts[-1]] = None
        else:
            raise Exception("%s not found" % (name))

        return data, parts[-1]
    
    # Return a list of all extant variables, with their sub variables, joined with '.'
    def list(self, var_list=None, sub_vars=None, data=None, excludehidden=True):
        data = data if data else self._data
        var_list = var_list if var_list else []
        sub_vars = sub_vars if sub_vars else []

        this_level = list(data)
        this_level.sort()

        # print("list: sub_vars %s this_level %s" % (sub_vars, this_level))
        for var in this_level:
            # Hide vars that start with '.' unless directed otherwise
            if not excludehidden or var[0] != '%':
                value = data[var]
                if isinstance(value, dict):
                    # Recurse for remainder of subvars
                    var_list = self.list(var_list, sub_vars + [ var ], value)
                else:
                    var_list.append(".".join(sub_vars + [ var ]))

        return var_list
        
    def set(self, name, value, define=False):
        data, lastpart = self._lookup(name, define)
        # print("ConfigData.set: data %s lastpart %s" % (data, lastpart))
        # if lastpart in data:
        if data[lastpart] != value:
            # print("ConfigData.set: lastpart '%s' of '%s' was '%s' is now '%s'" % (lastpart, name, data[lastpart], value))
            data[lastpart] = value
            self._dirty = True
    
    def get(self, name=None, default=''):
        if name != None:
            data, lastpart = self._lookup(name)
            value = data[lastpart]
        else:
            value = self._data

        return default if value == '' else value
    
    def delete(self, name):
        data, lastpart = self._lookup(name)
        del(data[lastpart])
        self._dirty = True

    def dirty(self):
        return self._dirty

    def flush(self, force=False):
        if self._dirty or force:
            if self._write != None:
                self._write(json.dumps(self._data))
                self._dirty = False
