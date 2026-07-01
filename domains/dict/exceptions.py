# domains/dict/exceptions.py — Dict domain exceptions


class DictTypeNotFoundError(Exception):
    def __init__(self, type_code: str):
        self.type_code = type_code
        super().__init__(f"字典类型 '{type_code}' 不存在")


class DictTypeAlreadyExistsError(Exception):
    def __init__(self, type_code: str):
        self.type_code = type_code
        super().__init__(f"字典类型 '{type_code}' 已存在")


class DictValueNotFoundError(Exception):
    def __init__(self, value_id: int):
        self.value_id = value_id
        super().__init__(f"字典值 ID={value_id} 不存在")


class DictValueDuplicateError(Exception):
    def __init__(self, type_code: str, value_key: str):
        self.type_code = type_code
        self.value_key = value_key
        super().__init__(f"字典值 '{value_key}' 在类型 '{type_code}' 下已存在")
