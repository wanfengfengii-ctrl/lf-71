from django import forms
from django.core.exceptions import ValidationError
from .models import (
    MaterialBatch, TensionTest, FatigueTest, DataAnomalyLog,
    MaterialProcessParam, BreakageFlowRecord,
    DefectType, DefectRecord, FractureDiagnosis,
    QualityIssue, ProcessRiskPoint,
)
from .utils import AnomalyDetector, ReboundRateCalculator


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
            'break_reason', 'is_flagged', 'flag_reason',
            'test_time', 'notes'
        ]
        widgets = {
            'test_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'break_reason': forms.Textarea(attrs={'rows': 2}),
            'flag_reason': forms.Textarea(attrs={'rows': 2}),
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
        is_flagged = cleaned_data.get('is_flagged')
        flag_reason = cleaned_data.get('flag_reason')

        if abnormal_break:
            if not break_reason or not str(break_reason).strip():
                self.add_error('break_reason', '异常断裂必须填写原因')

        if is_flagged:
            if not flag_reason or not str(flag_reason).strip():
                self.add_error('flag_reason', '标记为异常数据时必须填写原因')

        batch = self.batch or (self.instance.batch if self.instance.pk else None)
        if batch and batch.is_broken and self.instance.pk is None:
            raise forms.ValidationError(
                '该批次样本已断裂，不能继续新增测试记录'
            )

        if batch and batch.is_broken and self.instance.pk and not self.instance.is_broken:
            if is_broken is False:
                pass

        tension_force = cleaned_data.get('tension_force')
        elongation = cleaned_data.get('elongation')
        if batch and tension_force and elongation:
            self._check_anomaly_rules(batch, tension_force, elongation)

        return cleaned_data

    def _check_anomaly_rules(self, batch, tension_force, elongation):
        existing_tests = TensionTest.objects.filter(batch=batch, is_flagged=False)
        if self.instance.pk:
            existing_tests = existing_tests.exclude(pk=self.instance.pk)

        if not existing_tests.exists():
            return

        forces = list(existing_tests.values_list('tension_force', flat=True))
        elongations = list(existing_tests.values_list('elongation', flat=True))

        if forces:
            avg_force = sum(forces) / len(forces)
            if avg_force > 0 and abs(tension_force - avg_force) / avg_force > 0.5:
                self.add_error(
                    'tension_force',
                    f'该拉力值与批次平均值({avg_force:.1f}N)偏差超过50%，请确认数据是否正确或标记为异常数据'
                )

        if elongations:
            avg_elong = sum(elongations) / len(elongations)
            if avg_elong > 0 and abs(elongation - avg_elong) / avg_elong > 0.5:
                self.add_error(
                    'elongation',
                    f'该伸长量与批次平均值({avg_elong:.1f}mm)偏差超过50%，请确认数据是否正确或标记为异常数据'
                )

        if tension_force > 0 and elongation > 0 and forces and elongations:
            current_ratio = tension_force / elongation
            ratios = [f / e for f, e in zip(forces, elongations) if e > 0]
            if ratios:
                avg_ratio = sum(ratios) / len(ratios)
                if avg_ratio > 0 and abs(current_ratio - avg_ratio) / avg_ratio > 3.0:
                    self.add_error(
                        'tension_force',
                        f'拉力-伸长比值异常，当前比值 {current_ratio:.2f} 与批次均值 {avg_ratio:.2f} 偏差过大'
                    )


class FatigueTestForm(forms.ModelForm):
    class Meta:
        model = FatigueTest
        fields = [
            'load_force', 'cycle_count', 'frequency', 'load_ratio',
            'result', 'abnormal_break', 'break_reason',
            'elongation_after', 'is_flagged', 'flag_reason',
            'test_time', 'notes'
        ]
        widgets = {
            'test_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'break_reason': forms.Textarea(attrs={'rows': 2}),
            'flag_reason': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.batch = kwargs.pop('batch', None)
        super().__init__(*args, **kwargs)
        self.fields['test_time'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean_load_force(self):
        load_force = self.cleaned_data.get('load_force')
        if load_force is not None and load_force <= 0:
            raise forms.ValidationError('加载力必须大于0')
        return load_force

    def clean_cycle_count(self):
        cycle_count = self.cleaned_data.get('cycle_count')
        if cycle_count is not None and cycle_count <= 0:
            raise forms.ValidationError('循环次数必须大于0')
        return cycle_count

    def clean_frequency(self):
        frequency = self.cleaned_data.get('frequency')
        if frequency is not None and frequency <= 0:
            raise forms.ValidationError('频率必须大于0')
        return frequency

    def clean_load_ratio(self):
        load_ratio = self.cleaned_data.get('load_ratio')
        if load_ratio is not None and (load_ratio < -1 or load_ratio > 1):
            raise forms.ValidationError('应力比应在-1到1之间')
        return load_ratio

    def clean_elongation_after(self):
        value = self.cleaned_data.get('elongation_after')
        if value is not None and value < 0:
            raise forms.ValidationError('测试后伸长量不能为负数')
        return value

    def clean(self):
        cleaned_data = super().clean()
        is_flagged = cleaned_data.get('is_flagged')
        flag_reason = cleaned_data.get('flag_reason')
        abnormal_break = cleaned_data.get('abnormal_break')
        break_reason = cleaned_data.get('break_reason')
        result = cleaned_data.get('result')

        if abnormal_break:
            if not break_reason or not str(break_reason).strip():
                self.add_error('break_reason', '异常断裂必须填写原因')

        if result != FatigueTest.RESULT_BROKEN and abnormal_break:
            self.add_error('abnormal_break', '只有测试结果为"断裂"时才能标记异常断裂')

        if is_flagged:
            if not flag_reason or not str(flag_reason).strip():
                self.add_error('flag_reason', '标记为异常数据时必须填写原因')

        batch = self.batch or (self.instance.batch if self.instance.pk else None)
        if batch and not batch.can_add_fatigue_test():
            raise forms.ValidationError(
                '该批次处于断裂/审核/归档状态，不能新增疲劳测试记录'
            )

        if batch:
            load_force = cleaned_data.get('load_force')
            cycle_count = cleaned_data.get('cycle_count')
            if load_force and cycle_count:
                self._check_fatigue_anomaly_rules(batch, load_force, cycle_count)

        return cleaned_data

    def _check_fatigue_anomaly_rules(self, batch, load_force, cycle_count):
        existing = FatigueTest.objects.filter(batch=batch, is_flagged=False)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if not existing.exists():
            return

        cycles = list(existing.values_list('cycle_count', flat=True))
        loads = list(existing.values_list('load_force', flat=True))

        if cycles:
            avg_cycles = sum(cycles) / len(cycles)
            if avg_cycles > 0 and abs(cycle_count - avg_cycles) / avg_cycles > 0.6:
                self.add_error(
                    'cycle_count',
                    f'循环次数{cycle_count}与批次均值({avg_cycles:.0f})偏差超过60%，请确认数据'
                )

        if loads:
            avg_load = sum(loads) / len(loads)
            if avg_load > 0 and abs(load_force - avg_load) / avg_load > 0.5:
                self.add_error(
                    'load_force',
                    f'加载力{load_force}N与批次均值({avg_load:.1f}N)偏差超过50%，请确认数据'
                )


class BatchReviewForm(forms.Form):
    review_notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label='审核备注'
    )
    action = forms.ChoiceField(
        choices=[('archive', '确认归档'), ('reactivate', '恢复为正常')],
        label='审核操作',
        required=True
    )


class AnomalyResolveForm(forms.ModelForm):
    class Meta:
        model = DataAnomalyLog
        fields = ['resolution']
        widgets = {
            'resolution': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_resolution(self):
        resolution = self.cleaned_data.get('resolution')
        if not resolution or not str(resolution).strip():
            raise forms.ValidationError('处理说明不能为空')
        return resolution


class MaterialProcessParamForm(forms.ModelForm):
    class Meta:
        model = MaterialProcessParam
        fields = [
            'param_name', 'param_value', 'param_unit',
            'param_type', 'description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.batch = kwargs.pop('batch', None)
        super().__init__(*args, **kwargs)

    def clean_param_name(self):
        param_name = self.cleaned_data.get('param_name')
        if not param_name or not str(param_name).strip():
            raise forms.ValidationError('参数名称不能为空')
        if self.batch:
            qs = MaterialProcessParam.objects.filter(
                batch=self.batch, param_name=param_name
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('该参数名称已存在于此批次')
        return param_name

    def clean_param_value(self):
        value = self.cleaned_data.get('param_value')
        if value is None:
            raise forms.ValidationError('参数值不能为空')
        return value


class ProcessNoteForm(forms.Form):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=True,
        label='流程备注'
    )
    operator = forms.CharField(
        max_length=100,
        required=False,
        label='操作人'
    )


class DefectTypeForm(forms.ModelForm):
    class Meta:
        model = DefectType
        fields = [
            'defect_code', 'defect_name', 'category', 'severity',
            'description', 'typical_causes', 'detection_method',
            'prevention_measures', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'typical_causes': forms.Textarea(attrs={'rows': 2}),
            'detection_method': forms.Textarea(attrs={'rows': 2}),
            'prevention_measures': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_defect_code(self):
        defect_code = self.cleaned_data.get('defect_code')
        if DefectType.objects.filter(
                defect_code=defect_code
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('该缺陷编码已存在')
        return defect_code


class DefectRecordForm(forms.ModelForm):
    class Meta:
        model = DefectRecord
        fields = [
            'defect_type', 'defect_code', 'source_type', 'source_id',
            'defect_location', 'defect_size', 'description',
            'severity_assessment', 'root_cause', 'corrective_action',
            'preventive_action', 'detected_by', 'detected_at', 'notes'
        ]
        widgets = {
            'detected_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'description': forms.Textarea(attrs={'rows': 3}),
            'root_cause': forms.Textarea(attrs={'rows': 2}),
            'corrective_action': forms.Textarea(attrs={'rows': 2}),
            'preventive_action': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.batch = kwargs.pop('batch', None)
        super().__init__(*args, **kwargs)
        self.fields['detected_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['defect_type'].queryset = DefectType.objects.filter(is_active=True)

    def clean_defect_code(self):
        defect_code = self.cleaned_data.get('defect_code')
        if DefectRecord.objects.filter(
                defect_code=defect_code
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('该缺陷记录编号已存在')
        return defect_code


class FractureDiagnosisForm(forms.ModelForm):
    class Meta:
        model = FractureDiagnosis
        fields = [
            'diagnosis_code', 'source_test_type', 'source_test_id',
            'fracture_mode', 'fracture_location', 'fracture_surface',
            'primary_cause', 'root_cause_category', 'fracture_energy',
            'crack_propagation_rate', 'fatigue_crack_initiation_cycles',
            'diagnosis_conclusion', 'improvement_suggestions',
            'diagnosed_by', 'notes'
        ]
        widgets = {
            'fracture_surface': forms.Textarea(attrs={'rows': 2}),
            'primary_cause': forms.Textarea(attrs={'rows': 3}),
            'diagnosis_conclusion': forms.Textarea(attrs={'rows': 3}),
            'improvement_suggestions': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.batch = kwargs.pop('batch', None)
        super().__init__(*args, **kwargs)

    def clean_diagnosis_code(self):
        diagnosis_code = self.cleaned_data.get('diagnosis_code')
        if FractureDiagnosis.objects.filter(
                diagnosis_code=diagnosis_code
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('该诊断编号已存在')
        return diagnosis_code


class QualityIssueForm(forms.ModelForm):
    class Meta:
        model = QualityIssue
        fields = [
            'issue_code', 'issue_title', 'issue_type', 'priority',
            'description', 'impact_analysis', 'root_cause',
            'corrective_action', 'preventive_action',
            'related_defect_types', 'related_recipes',
            'raised_by', 'assigned_to', 'notes'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'impact_analysis': forms.Textarea(attrs={'rows': 2}),
            'root_cause': forms.Textarea(attrs={'rows': 2}),
            'corrective_action': forms.Textarea(attrs={'rows': 2}),
            'preventive_action': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['related_defect_types'].queryset = DefectType.objects.filter(is_active=True)

    def clean_issue_code(self):
        issue_code = self.cleaned_data.get('issue_code')
        if QualityIssue.objects.filter(
                issue_code=issue_code
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('该问题编号已存在')
        return issue_code


class ProcessRiskPointForm(forms.ModelForm):
    class Meta:
        model = ProcessRiskPoint
        fields = [
            'risk_code', 'risk_name', 'category', 'process_step',
            'related_param', 'description', 'potential_consequences',
            'likelihood', 'severity', 'detectability',
            'control_measures', 'mitigation_plan', 'is_monitored',
            'monitoring_method', 'related_defect_types',
            'identified_by', 'notes'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'potential_consequences': forms.Textarea(attrs={'rows': 2}),
            'control_measures': forms.Textarea(attrs={'rows': 2}),
            'mitigation_plan': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.recipe = kwargs.pop('recipe', None)
        super().__init__(*args, **kwargs)
        self.fields['related_defect_types'].queryset = DefectType.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        likelihood = cleaned_data.get('likelihood')
        severity = cleaned_data.get('severity')
        detectability = cleaned_data.get('detectability')

        for field, value in [('likelihood', likelihood), ('severity', severity), ('detectability', detectability)]:
            if value is not None and (value < 1 or value > 10):
                self.add_error(field, '评分必须在1-10之间')

        return cleaned_data


class DefectResolveForm(forms.Form):
    corrective_action = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=True,
        label='纠正措施'
    )
    preventive_action = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label='预防措施'
    )
    resolver = forms.CharField(
        max_length=100,
        required=False,
        label='处理人'
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='备注'
    )


class QualityIssueBatchForm(forms.Form):
    batch = forms.ModelChoiceField(
        queryset=MaterialBatch.objects.all(),
        required=True,
        label='材料批次'
    )
    impact_level = forms.ChoiceField(
        choices=[
            ('direct', '直接影响'),
            ('indirect', '间接影响'),
            ('potential', '潜在影响'),
        ],
        initial='potential',
        required=True,
        label='影响程度'
    )
    is_confirmed = forms.BooleanField(
        required=False,
        initial=False,
        label='是否确认'
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='备注'
    )
