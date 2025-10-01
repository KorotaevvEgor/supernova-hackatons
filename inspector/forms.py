from django import forms
from .models import InspectorViolation, ViolationPhoto, ViolationComment


class ViolationCommentForm(forms.ModelForm):
    """Форма для добавления комментариев к нарушениям"""
    
    class Meta:
        model = ViolationComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 pb-12 border-0 bg-transparent focus:outline-none focus:ring-0 placeholder-gray-400',
                'placeholder': 'Напишите ваш комментарий... Можно добавить дополнительную информацию о нарушении',
                'rows': 5,
                'maxlength': 1000,
                'style': 'resize: vertical; min-height: 120px; max-height: 300px; font-size: 14px; line-height: 1.5;'
            }),
        }
        labels = {
            'comment': 'Комментарий',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['comment'].required = True