from modeltranslation.translator import translator, TranslationOptions
from .models import Tariff


class TariffTranslationOptions(TranslationOptions):
    fields = ('title', 'description')


translator.register(Tariff, TariffTranslationOptions)
