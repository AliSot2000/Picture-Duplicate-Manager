import os


def rec_list_all(path: str):
    """
    Recursive list everything contained beneth this path.
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
