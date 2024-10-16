import os


def rec_list_all(path: str):
    """
    Recursive list everything contained within this path.
    :param path:
    :return:
    """
    files = os.listdir(path)
    results = []
    for file in files:
        file_path = os.path.join(path, file)
        if os.path.isdir(file_path):
            results.extend(rec_list_all(file_path))
        elif os.path.isfile(file_path):
            results.append(file_path)

    return results



def rec_walker(target, value: dict, types: dict):
    if type(target) is list or type(target) is tuple:
        for i in range(len(target)):
            if value.get(f"{i}") is None:
                value[f"{i}"] = {}

            if types.get(f"{i}") is None:
                types[f"{i}"] = {}

            v, t = rec_walker(target[i], value[f"{i}"], types[f"{i}"])
            value[f"{i}"] = v
            types[f"{i}"] = t
        return value, types
    elif type(target) is dict:
        for k, v in target.items():
            if value.get(k) is None:
                value[k] = {}

            if types.get(k) is None:
                types[k] = {}

            v, t = rec_walker(target[k], value[k], types[k])
            value[k] = v
            types[k] = t
        return value, types

    else:
        return target, type(target)


def path_builder(target, path: str = "", path_val: dict = None, path_type: dict = None):
    if path_val is None:
        path_val = {}
    if path_type is None:
        path_type = {}

    if type(target) is list or type(target) is tuple:
        for i in range(len(target)):
            val, tp = path_builder(target[i], path=f"{path}:{i}")

            for key in val.keys():
                if path_val.get(key) is None:
                    path_val[key] = val[key]

            for key in tp.keys():
                if path_type.get(key) is None:
                    path_type[key] = tp[key]

        return path_val, path_type
    elif type(target) is dict:
        for k, v in target.items():

            val, tp = path_builder(target[k], path=f"{path}:{k}")
            for key in val.keys():
                if path_val.get(key) is None:
                    path_val[key] = val[key]

            for key in tp.keys():
                if path_type.get(key) is None:
                    path_type[key] = tp[key]

        return path_val, path_type
    else:
        return {path: target}, {path: type(target)}