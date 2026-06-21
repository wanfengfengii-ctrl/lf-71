from django import forms
from .models import MaterialBatch, TensionTest


class MaterialBatchForm(forms.ModelForm):
    class Meta:
        model = MaterialBatch
        fields = [
            'batch_number', 'material_source', 'diameter',
            'initial_length', 'description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_batch_number(self):
        batch_number = self.cleaned_data.get('batch_number')
        if MaterialBatch.objects.filter(
                batch_number=batch_number
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('该批次编号已存在，请使用其他编号')
        return batch_number

    def clean_diameter(self):
        diameter = self.cleaned_data.get('diameter')
        if diameter is not None and diameter <= 0:
            raise forms.ValidationError('直径必须大于0')
        return diameter

    def clean_initial_length(self):
        initial_length = self.cleaned_data.get('initial_length')
        if initial_length is not None and initial_length <= 0:
            raise forms.ValidationError('初始长度必须大于0')
        return initial_length


class TensionTestForm(forms.ModelForm):
    class Meta:
        model = TensionTest
        fields = [
            'tension_force', 'elongation', 'length_before_rebound',
            'length_after_rebound', 'is_broken', 'abnormal_break',
            'break_reason', 'test_time', 'notes'
        ]
        widgets = {
            'test_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'break_reason': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.batch = kwargs.pop('batch', None)
        super().__init__(*args, **kwargs)
        self.fields['test_time'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean_tension_force(self):
        tension_force = self.cleaned_data.get('tension_force')
        if tension_force is not None and tension_force <= 0:
            raise forms.ValidationError('拉力值必须大于0')
        return tension_force

    def clean_elongation(self):
        elongation = self.cleaned_data.get('elongation')
        if elongation is not None and elongation < 0:
            raise forms.ValidationError('伸长量不能为负数')
        return elongation

    def clean_length_before_rebound(self):
        value = self.cleaned_data.get('length_before_rebound')
        if value is not None and value <= 0:
            raise forms.ValidationError('回弹前长度必须大于0')
        return value

    def clean_length_after_rebound(self):
        value = self.cleaned_data.get('length_after_rebound')
        if value is not None and value <= 0:
            raise forms.ValidationError('回弹后长度必须大于0')
        return value

    def clean(self):
        cleaned_data = super().clean()
        abnormal_break = cleaned_data.get('abnormal_break')
        break_reason = cleaned_data.get('break_reason')
        is_broken = cleaned_data.get('is_broken')

        if abnormal_break and break_reason and not break_reason.strip():
            self.add_error('break_reason', '异常断裂必须填写原因')

        batch = self.batch or (self.instance.batch if self.instance.pk else None)
        if batch:
            previous_broken = TensionTest.objects.filter(
                batch=batch, is_broken=True
            )
            if self.instance.pk:
                previous_broken = previous_broken.exclude(pk=self.instance.pk)
            if previous_broken.exists():
                raise forms.ValidationError(
                    '该批次样本已断裂，不能继续新增测试记录'
                )
        return cleaned_data
