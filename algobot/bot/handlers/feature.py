from aiogram import Router
from aiogram.dispatcher.event.handler import HandlerObject, CallbackType
from aiogram.filters import Command

from algobot.utils.dict_propagator import DictPropagator


class InvalidFeatureNameError(Exception):
    def __init__(self, feature_name: str):
        self.feature_name = feature_name
        super().__init__(
            f'Invalid feature name `{feature_name}`, '
            f'should contain only lowercase letters'
        )


class NonUniqueFeatureNameError(Exception):
    def __init__(self, feature_name: str):
        self.feature_name = feature_name
        super().__init__(f'Feature name `{feature_name}` is already registered')


class NoEntryPointError(Exception):
    def __init__(self, feature: 'EnablerRouter'):
        self.feature = feature
        super().__init__(f'Feature `{feature.feature_name}` has no entry point')


class EnablerRouter(Router, metaclass=DictPropagator, field_name='_features'):
    _features: dict[str, 'EnablerRouter'] = {}

    def __init__(
        self,
        feature_name: str,
        enabled_by_default: bool = True,
        *args,
        **kwargs,
    ):
        if not feature_name.isalpha() or not feature_name.islower():
            raise InvalidFeatureNameError(feature_name)
        super().__init__(*args, **kwargs)
        self.feature_name = feature_name
        self.enabled_by_default = enabled_by_default
        self.is_enabled = enabled_by_default
        self.entry_points: list[HandlerObject] = []
        self._register()

    def _register(self):
        if self.feature_name in EnablerRouter._features:
            raise NonUniqueFeatureNameError(self.feature_name)
        EnablerRouter._features[self.feature_name] = self

    def entry_point(self, *filters: CallbackType, **kwargs):
        command_name = kwargs.pop('command', self.feature_name)

        def decorator(handler: CallbackType):
            self.message.register(
                handler,
                Command(command_name),
                *filters,
                flags={'feature': True, 'enabled': self.enabled_by_default, 'chat_action': {
                    'action': 'typing',
                    'initial_sleep': 0,
                    'interval': 0.5
                }},
                **kwargs,
            )
            self.entry_points.append(self.message.handlers[-1])
            return handler

        return decorator

    async def toggle(self, enable: bool):
        for entry_point in self.entry_points:
            entry_point.flags.update(enabled=enable)
        self.is_enabled = enable
