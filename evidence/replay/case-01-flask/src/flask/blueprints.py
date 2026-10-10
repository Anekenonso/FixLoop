class Blueprint:
    def __init__(self, name, import_name):
        if '.' in name:
            raise ValueError("Blueprint name must not contain a dot '.' character.")
        self.name = name
        self.import_name = import_name
