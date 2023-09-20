class DictPropagator(type):
    def __new__(metacls, name, bases, class_dict, field_name: str):
        cls = super().__new__(metacls, name, bases, class_dict)
        cls._propagated_field = field_name
        return cls

    def __iter__(cls):
        attr = getattr(cls, cls._propagated_field)
        return iter(attr.items())

    def __getitem__(cls, item):
        attr = getattr(cls, cls._propagated_field)
        return attr.get(item, None)
