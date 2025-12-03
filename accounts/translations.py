from modeltranslation.translator import translator, TranslationOptions
from accounts.models import AdditionalInfo


class AdditionalInfoTranslationOptions(TranslationOptions):
    """Translation options for AdditionalInfo model"""
    fields = ('help_text', 'description', 'about_us', 'working_hours')


translator.register(AdditionalInfo, AdditionalInfoTranslationOptions)