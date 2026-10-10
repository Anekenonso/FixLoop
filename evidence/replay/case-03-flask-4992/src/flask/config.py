import os

class Config(dict):
    def __init__(self, root_path=""):
        super().__init__()
        self.root_path = root_path

    def from_file(self, filename, load, silent=False, text=True):
        filename = os.path.join(self.root_path, filename)
        mode = "r" if text else "rb"
        with open(filename, mode) as f:
            obj = load(f)
        self.update(obj)
        return True
