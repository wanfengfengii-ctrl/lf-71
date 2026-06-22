from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class BreakageFlowRecord(models.Model):
    ACTION_DETECTED = 'detected'
    ACTION_REVIEW_START = 'review_start'
    ACTION_ARCHIVED = 'archived'
    ACTION_REACTIVATED = 'reactivated'
    ACTION_NOTE_ADDED = 'note_added'

    ACTION_CHOICES = [
        (ACTION_DETECTED, '断裂检测'),
        (ACTION_REVIEW_START, '开始审核'),
        (ACTION_ARCHIVED, '审核通过-归档'),
        (ACTION_REACTIVATED, '恢复正常'),
        (ACTION_NOTE_ADDED, '添加备注'),
    ]

    batch = models.ForeignKey(
        'MaterialBatch',
        on_delete=models.CASCADE,
        related_name='flow_records',
        verbose_name='材料批次'
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        verbose_name='流程动作'
    )
    operator = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='操作人'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='流程备注'
    )
    source_test_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='关联测试ID'
    )
    source_test_type = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='关联测试类型'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='记录时间'
    )

    class Meta:
        verbose_name = '断裂流程记录'
        verbose_name_plural = '断裂流程记录'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.batch.batch_number} - {self.get_action_display()}'


class MaterialProcessParam(models.Model):
    PARAM_TYPE_MATERIAL = 'material'
    PARAM_TYPE_PROCESS = 'process'
    PARAM_TYPE_ENVIRONMENT = 'environment'

    PARAM_TYPE_CHOICES = [
        (PARAM_TYPE_MATERIAL, '材料属性'),
        (PARAM_TYPE_PROCESS, '工艺参数'),
        (PARAM_TYPE_ENVIRONMENT, '环境条件'),
    ]

    batch = models.ForeignKey(
        'MaterialBatch',
        on_delete=models.CASCADE,
        related_name='process_params',
        verbose_name='材料批次'
    )
    param_name = models.CharField(
        max_length=100,
        verbose_name='参数名称'
    )
    param_value = models.FloatField(
        verbose_name='参数值'
    )
    param_unit = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='单位'
    )
    param_type = models.CharField(
        max_length=20,
        choices=PARAM_TYPE_CHOICES,
        default=PARAM_TYPE_MATERIAL,
        verbose_name='参数类型'
    )
    description = models.TextField(
        blank=True,
        verbose_name='参数说明'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='记录时间'
    )

    class Meta:
        verbose_name = '材料工艺参数'
        verbose_name_plural = '材料工艺参数'
        ordering = ['param_type', 'param_name']
        unique_together = [['batch', 'param_name']]

    def __str__(self):
        return f'{self.batch.batch_number} - {self.param_name}: {self.param_value}{self.param_unit}'

    def clean(self):
        if self.param_value is None:
            raise ValidationError({'param_value': '参数值不能为空'})
        super().clean()


class StatisticalSnapshot(models.Model):
    SNAPSHOT_TYPE_DAILY = 'daily'
    SNAPSHOT_TYPE_WEEKLY = 'weekly'
    SNAPSHOT_TYPE_MONTHLY = 'monthly'

    SNAPSHOT_TYPE_CHOICES = [
        (SNAPSHOT_TYPE_DAILY, '每日'),
        (SNAPSHOT_TYPE_WEEKLY, '每周'),
        (SNAPSHOT_TYPE_MONTHLY, '每月'),
    ]

    snapshot_date = models.DateField(
        verbose_name='快照日期'
    )
    snapshot_type = models.CharField(
        max_length=20,
        choices=SNAPSHOT_TYPE_CHOICES,
        default=SNAPSHOT_TYPE_DAILY,
        verbose_name='快照类型'
    )
    total_batches = models.PositiveIntegerField(
        default=0,
        verbose_name='总批次数'
    )
    active_batches = models.PositiveIntegerField(
        default=0,
        verbose_name='正常批次数'
    )
    broken_batches = models.PositiveIntegerField(
        default=0,
        verbose_name='已断裂批次数'
    )
    total_tension_tests = models.PositiveIntegerField(
        default=0,
        verbose_name='总拉伸测试数'
    )
    total_fatigue_tests = models.PositiveIntegerField(
        default=0,
        verbose_name='总疲劳测试数'
    )
    avg_force = models.FloatField(
        null=True,
        blank=True,
        verbose_name='平均拉力(N)'
    )
    avg_elongation = models.FloatField(
        null=True,
        blank=True,
        verbose_name='平均伸长量(mm)'
    )
    avg_rebound_rate = models.FloatField(
        null=True,
        blank=True,
        verbose_name='平均回弹率(%)'
    )
    anomaly_count = models.PositiveIntegerField(
        default=0,
        verbose_name='异常数据数'
    )
    resolved_anomaly_count = models.PositiveIntegerField(
        default=0,
        verbose_name='已处理异常数'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '统计快照'
        verbose_name_plural = '统计快照'
        ordering = ['-snapshot_date']
        unique_together = [['snapshot_date', 'snapshot_type']]

    def __str__(self):
        return f'{self.snapshot_date} - {self.get_snapshot_type_display()}统计'


class MaterialBatch(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_TESTING = 'testing'
    STATUS_BROKEN = 'broken'
    STATUS_REVIEW = 'review'
    STATUS_ARCHIVED = 'archived'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, '正常'),
        (STATUS_TESTING, '测试中'),
        (STATUS_BROKEN, '已断裂'),
        (STATUS_REVIEW, '待审核'),
        (STATUS_ARCHIVED, '已归档'),
    ]

    batch_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='批次编号',
        help_text='材料批次编号，必须唯一'
    )
    material_source = models.CharField(
        max_length=200,
        verbose_name='材料来源',
        help_text='材料的产地或供应商'
    )
    diameter = models.FloatField(
        verbose_name='直径(mm)',
        help_text='材料直径，单位毫米，必须大于0'
    )
    initial_length = models.FloatField(
        verbose_name='初始长度(mm)',
        help_text='材料初始长度，单位毫米，必须大于0'
    )
    description = models.TextField(
        blank=True,
        verbose_name='备注说明'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        verbose_name='批次状态',
        help_text='批次当前流程状态'
    )
    broken_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='断裂时间',
        help_text='样本断裂的时间'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='审核时间',
        help_text='断裂审核完成的时间'
    )
    review_notes = models.TextField(
        blank=True,
        verbose_name='审核备注',
        help_text='断裂审核时的备注说明'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '材料批次'
        verbose_name_plural = '材料批次'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.batch_number} - {self.material_source}'

    def clean(self):
        if self.diameter is not None and self.diameter <= 0:
            raise ValidationError({'diameter': '直径必须大于0'})
        if self.initial_length is not None and self.initial_length <= 0:
            raise ValidationError({'initial_length': '初始长度必须大于0'})
        super().clean()

    @property
    def is_broken(self):
        return self.status in (self.STATUS_BROKEN, self.STATUS_REVIEW)

    @property
    def latest_test(self):
        return self.tension_tests.order_by('-test_time').first()

    @property
    def test_count(self):
        return self.tension_tests.count()

    @property
    def fatigue_test_count(self):
        return self.fatigue_tests.count()

    @property
    def max_tension_force(self):
        test = self.tension_tests.order_by('-tension_force').first()
        return test.tension_force if test else None

    @property
    def max_elongation(self):
        test = self.tension_tests.order_by('-elongation').first()
        return test.elongation if test else None

    @property
    def avg_rebound_rate(self):
        tests = self.tension_tests.filter(rebound_rate__isnull=False)
        if not tests.exists():
            return None
        return round(sum(t.rebound_rate for t in tests) / tests.count(), 2)

    @property
    def anomaly_count(self):
        return self.anomaly_logs.filter(is_resolved=False).count()

    def can_add_test(self):
        return self.status not in (self.STATUS_BROKEN, self.STATUS_REVIEW, self.STATUS_ARCHIVED)

    def can_add_fatigue_test(self):
        return self.status not in (self.STATUS_BROKEN, self.STATUS_REVIEW, self.STATUS_ARCHIVED)

    @property
    def youngs_modulus(self):
        tests = self.tension_tests.filter(is_flagged=False, is_broken=False)
        if not tests.exists() or self.diameter <= 0 or self.initial_length <= 0:
            return None
        area = 3.1415926535 * (self.diameter / 2) ** 2
        if area <= 0:
            return None
        moduli = []
        for test in tests:
            if test.elongation > 0:
                stress = test.tension_force / area
                strain = test.elongation / self.initial_length
                if strain > 0:
                    moduli.append(stress / strain)
        if moduli:
            return round(sum(moduli) / len(moduli), 2)
        return None

    @property
    def breaking_force(self):
        broken_tests = self.tension_tests.filter(is_broken=True)
        if not broken_tests.exists():
            return None
        return broken_tests.order_by('-tension_force').first().tension_force

    @property
    def breaking_elongation(self):
        broken_tests = self.tension_tests.filter(is_broken=True)
        if not broken_tests.exists():
            return None
        return broken_tests.order_by('-elongation').first().elongation

    @property
    def tensile_strength(self):
        if self.breaking_force is None or self.diameter <= 0:
            return None
        area = 3.1415926535 * (self.diameter / 2) ** 2
        if area <= 0:
            return None
        return round(self.breaking_force / area, 2)

    @property
    def elongation_at_break(self):
        if self.breaking_elongation is None or self.initial_length <= 0:
            return None
        return round((self.breaking_elongation / self.initial_length) * 100, 2)

    @property
    def flow_record_count(self):
        return self.flow_records.count()

    @property
    def process_param_count(self):
        return self.process_params.count()

    @property
    def latest_flow_record(self):
        return self.flow_records.first()

    def record_flow_action(self, action, notes='', operator='', source_test_id=None, source_test_type=''):
        return BreakageFlowRecord.objects.create(
            batch=self,
            action=action,
            notes=notes,
            operator=operator,
            source_test_id=source_test_id,
            source_test_type=source_test_type,
        )

    @property
    def fatigue_cycles_to_failure(self):
        broken_fatigue = self.fatigue_tests.filter(result=FatigueTest.RESULT_BROKEN)
        if not broken_fatigue.exists():
            return None
        return broken_fatigue.order_by('-cycle_count').first().cycle_count

    @property
    def fatigue_endurance_limit(self):
        intact_tests = self.fatigue_tests.filter(
            result__in=[FatigueTest.RESULT_INTACT, FatigueTest.RESULT_MINOR_DAMAGE]
        )
        if not intact_tests.exists():
            return None
        return intact_tests.order_by('-load_force').first().load_force

    def get_statistics_summary(self):
        tests = self.tension_tests.filter(is_flagged=False)
        fatigue_tests = self.fatigue_tests.filter(is_flagged=False)
        stats = {
            'tension_test_count': tests.count(),
            'fatigue_test_count': fatigue_tests.count(),
            'anomaly_count': self.anomaly_count,
            'flow_record_count': self.flow_record_count,
        }
        if tests.exists():
            forces = list(tests.values_list('tension_force', flat=True))
            elongations = list(tests.values_list('elongation', flat=True))
            rebounds = list(tests.filter(rebound_rate__isnull=False).values_list('rebound_rate', flat=True))
            stats.update({
                'avg_force': round(sum(forces) / len(forces), 2),
                'max_force': max(forces),
                'min_force': min(forces),
                'avg_elongation': round(sum(elongations) / len(elongations), 2),
                'max_elongation': max(elongations),
                'avg_rebound': round(sum(rebounds) / len(rebounds), 2) if rebounds else None,
                'youngs_modulus': self.youngs_modulus,
                'tensile_strength': self.tensile_strength,
                'elongation_at_break': self.elongation_at_break,
            })
        return stats


class TensionTest(models.Model):
    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='tension_tests',
        verbose_name='材料批次'
    )
    tension_force = models.FloatField(
        verbose_name='拉力值(N)',
        help_text='施加的拉力，单位牛顿，必须大于0'
    )
    elongation = models.FloatField(
        verbose_name='伸长量(mm)',
        help_text='拉伸后的伸长量，单位毫米，不能为负数'
    )
    length_before_rebound = models.FloatField(
        null=True,
        blank=True,
        verbose_name='回弹前长度(mm)',
        help_text='卸载拉力前的长度，用于计算回弹率'
    )
    length_after_rebound = models.FloatField(
        null=True,
        blank=True,
        verbose_name='回弹后长度(mm)',
        help_text='卸载拉力恢复后的长度，用于计算回弹率'
    )
    rebound_rate = models.FloatField(
        null=True,
        blank=True,
        verbose_name='回弹率(%)',
        help_text='自动计算的回弹率'
    )
    is_broken = models.BooleanField(
        default=False,
        verbose_name='是否断裂'
    )
    abnormal_break = models.BooleanField(
        default=False,
        verbose_name='异常断裂',
        help_text='是否为异常断裂'
    )
    break_reason = models.TextField(
        blank=True,
        verbose_name='断裂原因',
        help_text='异常断裂时必须填写原因'
    )
    is_flagged = models.BooleanField(
        default=False,
        verbose_name='数据异常标记',
        help_text='该数据被标记为异常数据'
    )
    flag_reason = models.TextField(
        blank=True,
        verbose_name='异常标记原因',
        help_text='数据被标记为异常的原因'
    )
    test_time = models.DateTimeField(
        default=timezone.now,
        verbose_name='测试时间'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='测试备注'
    )

    class Meta:
        verbose_name = '拉伸测试记录'
        verbose_name_plural = '拉伸测试记录'
        ordering = ['-test_time']

    def __str__(self):
        status = '已断裂' if self.is_broken else '正常'
        batch_no = getattr(self, 'batch_id', None)
        if batch_no:
            try:
                batch_info = str(self.batch.batch_number)
            except Exception:
                batch_info = f'#{batch_no}'
        else:
            batch_info = '未绑定批次'
        return f'{batch_info} - {self.tension_force}N - {status}'

    def clean(self):
        if self.tension_force is not None and self.tension_force <= 0:
            raise ValidationError({'tension_force': '拉力值必须大于0'})
        if self.elongation is not None and self.elongation < 0:
            raise ValidationError({'elongation': '伸长量不能为负数'})
        if self.length_before_rebound is not None:
            if self.length_before_rebound <= 0:
                raise ValidationError({'length_before_rebound': '回弹前长度必须大于0'})
        if self.length_after_rebound is not None:
            if self.length_after_rebound <= 0:
                raise ValidationError({'length_after_rebound': '回弹后长度必须大于0'})
        if self.abnormal_break:
            if not self.break_reason or not str(self.break_reason).strip():
                raise ValidationError({'break_reason': '异常断裂必须填写原因'})
        batch_id = getattr(self, 'batch_id', None)
        if batch_id:
            batch = MaterialBatch.objects.filter(pk=batch_id).first()
            if batch and not batch.can_add_test():
                if self.pk is None:
                    raise ValidationError('该批次样本已断裂或处于审核/归档状态，不能继续新增测试记录')
                else:
                    existing_broken = TensionTest.objects.filter(
                        batch_id=batch_id, is_broken=True
                    ).exclude(pk=self.pk)
                    if existing_broken.exists() and not self.is_broken:
                        pass
                    elif self.is_broken and existing_broken.exists():
                        pass
        super().clean()

    @property
    def stress(self):
        if not self.batch_id or self.batch.diameter <= 0:
            return None
        area = 3.1415926535 * (self.batch.diameter / 2) ** 2
        if area <= 0:
            return None
        return round(self.tension_force / area, 2)

    @property
    def strain(self):
        if not self.batch_id or self.batch.initial_length <= 0:
            return None
        return round(self.elongation / self.batch.initial_length, 6)

    def save(self, *args, **kwargs):
        if (self.length_before_rebound is not None
                and self.length_after_rebound is not None
                and self.elongation > 0):
            batch_id = getattr(self, 'batch_id', None)
            if batch_id:
                try:
                    if self.batch_id and MaterialBatch.objects.filter(pk=self.batch_id).exists():
                        initial = MaterialBatch.objects.get(pk=self.batch_id).initial_length
                    else:
                        initial = None
                except MaterialBatch.DoesNotExist:
                    initial = None
            else:
                initial = None
            if initial is not None:
                elastic_deformation = self.length_before_rebound - initial
                if elastic_deformation > 0:
                    rebound = self.length_before_rebound - self.length_after_rebound
                    self.rebound_rate = round((rebound / elastic_deformation) * 100, 2)
                else:
                    self.rebound_rate = None
            else:
                self.rebound_rate = None
        else:
            self.rebound_rate = None

        was_broken_before = False
        if self.pk:
            old = TensionTest.objects.filter(pk=self.pk).first()
            was_broken_before = old.is_broken if old else False

        is_new = self.pk is None
        super().save(*args, **kwargs)

        if self.is_broken and self.batch_id and not was_broken_before:
            batch = MaterialBatch.objects.filter(pk=self.batch_id).first()
            if batch and batch.status not in (MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW):
                batch.status = MaterialBatch.STATUS_BROKEN
                batch.broken_at = timezone.now()
                batch.save(update_fields=['status', 'broken_at'])
                batch.record_flow_action(
                    action=BreakageFlowRecord.ACTION_DETECTED,
                    notes=f'拉伸测试断裂 - 拉力:{self.tension_force}N, 伸长量:{self.elongation}mm',
                    source_test_id=self.pk,
                    source_test_type='tension',
                )


class FatigueTest(models.Model):
    RESULT_INTACT = 'intact'
    RESULT_MINOR_DAMAGE = 'minor_damage'
    RESULT_MAJOR_DAMAGE = 'major_damage'
    RESULT_BROKEN = 'broken'

    RESULT_CHOICES = [
        (RESULT_INTACT, '完好'),
        (RESULT_MINOR_DAMAGE, '轻微损伤'),
        (RESULT_MAJOR_DAMAGE, '严重损伤'),
        (RESULT_BROKEN, '断裂'),
    ]

    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='fatigue_tests',
        verbose_name='材料批次'
    )
    load_force = models.FloatField(
        verbose_name='加载力(N)',
        help_text='疲劳测试施加的循环载荷，单位牛顿，必须大于0'
    )
    cycle_count = models.IntegerField(
        verbose_name='循环次数',
        help_text='疲劳测试的循环加载次数，必须大于0'
    )
    frequency = models.FloatField(
        verbose_name='频率(Hz)',
        help_text='循环加载频率，单位赫兹，必须大于0'
    )
    load_ratio = models.FloatField(
        null=True,
        blank=True,
        verbose_name='应力比(R)',
        help_text='最小应力与最大应力之比，通常为-1到1之间'
    )
    result = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default=RESULT_INTACT,
        verbose_name='测试结果',
        help_text='疲劳测试后的样本状态'
    )
    abnormal_break = models.BooleanField(
        default=False,
        verbose_name='异常断裂',
        help_text='是否为异常断裂'
    )
    break_reason = models.TextField(
        blank=True,
        verbose_name='断裂原因',
        help_text='异常断裂时必须填写原因'
    )
    elongation_after = models.FloatField(
        null=True,
        blank=True,
        verbose_name='测试后伸长量(mm)',
        help_text='疲劳测试完成后的残余伸长量'
    )
    is_flagged = models.BooleanField(
        default=False,
        verbose_name='数据异常标记',
        help_text='该数据被标记为异常数据'
    )
    flag_reason = models.TextField(
        blank=True,
        verbose_name='异常标记原因'
    )
    test_time = models.DateTimeField(
        default=timezone.now,
        verbose_name='测试时间'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='测试备注'
    )

    class Meta:
        verbose_name = '疲劳测试记录'
        verbose_name_plural = '疲劳测试记录'
        ordering = ['-test_time']

    def __str__(self):
        return f'{self.batch.batch_number} - {self.load_force}N x {self.cycle_count}次'

    @property
    def stress_amplitude(self):
        if not self.batch_id or self.batch.diameter <= 0:
            return None
        area = 3.1415926535 * (self.batch.diameter / 2) ** 2
        if area <= 0:
            return None
        max_stress = self.load_force / area
        min_stress = self.load_ratio * max_stress if self.load_ratio is not None else -max_stress
        return round(abs(max_stress - min_stress) / 2, 2)

    @property
    def mean_stress(self):
        if not self.batch_id or self.batch.diameter <= 0:
            return None
        area = 3.1415926535 * (self.batch.diameter / 2) ** 2
        if area <= 0:
            return None
        max_stress = self.load_force / area
        min_stress = self.load_ratio * max_stress if self.load_ratio is not None else -max_stress
        return round((max_stress + min_stress) / 2, 2)

    @property
    def damage_severity(self):
        if self.result == self.RESULT_BROKEN:
            return 1.0
        elif self.result == self.RESULT_MAJOR_DAMAGE:
            return 0.7
        elif self.result == self.RESULT_MINOR_DAMAGE:
            return 0.3
        return 0.0

    def clean(self):
        if self.load_force is not None and self.load_force <= 0:
            raise ValidationError({'load_force': '加载力必须大于0'})
        if self.cycle_count is not None and self.cycle_count <= 0:
            raise ValidationError({'cycle_count': '循环次数必须大于0'})
        if self.frequency is not None and self.frequency <= 0:
            raise ValidationError({'frequency': '频率必须大于0'})
        if self.load_ratio is not None and (self.load_ratio < -1 or self.load_ratio > 1):
            raise ValidationError({'load_ratio': '应力比应在-1到1之间'})
        if self.elongation_after is not None and self.elongation_after < 0:
            raise ValidationError({'elongation_after': '测试后伸长量不能为负数'})
        if self.abnormal_break:
            if not self.break_reason or not str(self.break_reason).strip():
                raise ValidationError({'break_reason': '异常断裂必须填写原因'})
        batch_id = getattr(self, 'batch_id', None)
        if batch_id:
            batch = MaterialBatch.objects.filter(pk=batch_id).first()
            if batch and not batch.can_add_fatigue_test():
                raise ValidationError('该批次处于断裂/审核/归档状态，不能新增疲劳测试记录')
        super().clean()

    def save(self, *args, **kwargs):
        was_broken_before = False
        if self.pk:
            old = FatigueTest.objects.filter(pk=self.pk).first()
            was_broken_before = (old.result == self.RESULT_BROKEN) if old else False

        super().save(*args, **kwargs)
        if self.result == self.RESULT_BROKEN and self.batch_id and not was_broken_before:
            batch = MaterialBatch.objects.filter(pk=self.batch_id).first()
            if batch and batch.status not in (MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW):
                batch.status = MaterialBatch.STATUS_BROKEN
                batch.broken_at = timezone.now()
                batch.save(update_fields=['status', 'broken_at'])
                flow_notes = f'疲劳测试断裂 - 加载力:{self.load_force}N, 循环次数:{self.cycle_count}次'
                if self.abnormal_break:
                    flow_notes += f'【异常断裂】{self.break_reason}'
                batch.record_flow_action(
                    action=BreakageFlowRecord.ACTION_DETECTED,
                    notes=flow_notes,
                    source_test_id=self.pk,
                    source_test_type='fatigue',
                )


class DataAnomalyLog(models.Model):
    SEVERITY_LOW = 'low'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_HIGH = 'high'

    SEVERITY_CHOICES = [
        (SEVERITY_LOW, '低'),
        (SEVERITY_MEDIUM, '中'),
        (SEVERITY_HIGH, '高'),
    ]

    SOURCE_TENSION = 'tension'
    SOURCE_FATIGUE = 'fatigue'

    SOURCE_CHOICES = [
        (SOURCE_TENSION, '拉伸测试'),
        (SOURCE_FATIGUE, '疲劳测试'),
    ]

    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='anomaly_logs',
        verbose_name='材料批次'
    )
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        verbose_name='数据来源类型'
    )
    source_id = models.PositiveIntegerField(
        verbose_name='来源记录ID'
    )
    anomaly_description = models.TextField(
        verbose_name='异常描述',
        help_text='描述检测到的异常情况'
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_MEDIUM,
        verbose_name='严重程度'
    )
    is_resolved = models.BooleanField(
        default=False,
        verbose_name='是否已处理'
    )
    resolution = models.TextField(
        blank=True,
        verbose_name='处理说明',
        help_text='异常数据处理说明'
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='处理时间'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '异常数据日志'
        verbose_name_plural = '异常数据日志'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.batch.batch_number} - {self.get_severity_display()} - {self.anomaly_description[:30]}'


class BowType(models.Model):
    CATEGORY_TRADITIONAL = 'traditional'
    CATEGORY_COMPOUND = 'compound'
    CATEGORY_RECURVE = 'recurve'
    CATEGORY_LONGBOW = 'longbow'
    CATEGORY_CROSSBOW = 'crossbow'

    CATEGORY_CHOICES = [
        (CATEGORY_TRADITIONAL, '传统弓'),
        (CATEGORY_COMPOUND, '复合弓'),
        (CATEGORY_RECURVE, '反曲弓'),
        (CATEGORY_LONGBOW, '长弓'),
        (CATEGORY_CROSSBOW, '弩'),
    ]

    name = models.CharField(
        max_length=100,
        verbose_name='弓型名称'
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_TRADITIONAL,
        verbose_name='弓型类别'
    )
    min_draw_weight = models.FloatField(
        verbose_name='最小拉力要求(lbs)',
        help_text='弓的最小拉力要求，单位磅'
    )
    max_draw_weight = models.FloatField(
        verbose_name='最大拉力要求(lbs)',
        help_text='弓的最大拉力要求，单位磅'
    )
    draw_length = models.FloatField(
        verbose_name='拉距(英寸)',
        help_text='标准拉距，单位英寸'
    )
    recommended_diameter_min = models.FloatField(
        verbose_name='推荐弓弦最小直径(mm)',
        help_text='推荐弓弦材料的最小直径'
    )
    recommended_diameter_max = models.FloatField(
        verbose_name='推荐弓弦最大直径(mm)',
        help_text='推荐弓弦材料的最大直径'
    )
    min_tensile_strength = models.FloatField(
        verbose_name='最低抗拉强度要求(MPa)',
        help_text='弓弦材料的最低抗拉强度要求'
    )
    min_fatigue_cycles = models.IntegerField(
        verbose_name='最低疲劳循环次数要求',
        help_text='弓弦材料在标准载荷下的最低循环次数要求'
    )
    description = models.TextField(
        blank=True,
        verbose_name='弓型说明'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '弓型配置'
        verbose_name_plural = '弓型配置'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.get_category_display()} - {self.name}'

    def lbs_to_newtons(self, lbs):
        return round(lbs * 4.44822, 2)

    @property
    def min_draw_force_newtons(self):
        return self.lbs_to_newtons(self.min_draw_weight)

    @property
    def max_draw_force_newtons(self):
        return self.lbs_to_newtons(self.max_draw_weight)


class LifePrediction(models.Model):
    RISK_LEVEL_LOW = 'low'
    RISK_LEVEL_MEDIUM = 'medium'
    RISK_LEVEL_HIGH = 'high'
    RISK_LEVEL_CRITICAL = 'critical'

    RISK_LEVEL_CHOICES = [
        (RISK_LEVEL_LOW, '低风险'),
        (RISK_LEVEL_MEDIUM, '中风险'),
        (RISK_LEVEL_HIGH, '高风险'),
        (RISK_LEVEL_CRITICAL, '极高风险'),
    ]

    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='life_predictions',
        verbose_name='材料批次'
    )
    life_score = models.FloatField(
        verbose_name='寿命评分(0-100)',
        help_text='综合耐久性评分，0-100分'
    )
    durability_score = models.FloatField(
        verbose_name='耐久性评分',
        help_text='基于拉伸和疲劳测试的耐久性评分'
    )
    stability_score = models.FloatField(
        verbose_name='稳定性评分',
        help_text='基于回弹率和数据一致性的稳定性评分'
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        verbose_name='断裂风险等级'
    )
    risk_score = models.FloatField(
        verbose_name='风险指数(0-100)',
        help_text='断裂风险指数，越高风险越大'
    )
    predicted_cycles_to_failure = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='预测断裂循环次数'
    )
    predicted_lifetime_hours = models.FloatField(
        null=True,
        blank=True,
        verbose_name='预计使用寿命(小时)'
    )
    key_factors = models.JSONField(
        default=list,
        verbose_name='关键影响因素'
    )
    warning_signs = models.JSONField(
        default=list,
        verbose_name='预警信号'
    )
    recommendations = models.TextField(
        blank=True,
        verbose_name='优化建议'
    )
    predicted_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='预测时间'
    )
    is_latest = models.BooleanField(
        default=True,
        verbose_name='是否为最新预测'
    )

    class Meta:
        verbose_name = '寿命预测记录'
        verbose_name_plural = '寿命预测记录'
        ordering = ['-predicted_at']

    def __str__(self):
        return f'{self.batch.batch_number} - 评分:{self.life_score:.1f} - {self.get_risk_level_display()}'

    def save(self, *args, **kwargs):
        if self.is_latest:
            LifePrediction.objects.filter(
                batch=self.batch,
                is_latest=True
            ).exclude(pk=self.pk).update(is_latest=False)
        super().save(*args, **kwargs)

    @property
    def risk_color_class(self):
        mapping = {
            self.RISK_LEVEL_LOW: 'badge-success',
            self.RISK_LEVEL_MEDIUM: 'badge-warning',
            self.RISK_LEVEL_HIGH: 'badge-danger',
            self.RISK_LEVEL_CRITICAL: 'badge-danger',
        }
        return mapping.get(self.risk_level, 'badge-gray')


class MaterialRecommendation(models.Model):
    source_batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='recommendations_from',
        verbose_name='源材料批次'
    )
    recommended_batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='recommendations_to',
        verbose_name='推荐材料批次'
    )
    similarity_score = models.FloatField(
        verbose_name='相似度评分(0-100)',
        help_text='材料属性相似度评分'
    )
    performance_score = models.FloatField(
        verbose_name='性能提升评分',
        help_text='推荐材料相对于源材料的性能提升'
    )
    overall_score = models.FloatField(
        verbose_name='综合推荐评分',
        help_text='综合相似度和性能提升的推荐评分'
    )
    similarity_factors = models.JSONField(
        default=dict,
        verbose_name='相似度因素详情'
    )
    advantages = models.JSONField(
        default=list,
        verbose_name='推荐优势'
    )
    caveats = models.JSONField(
        default=list,
        verbose_name='注意事项'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='推荐时间'
    )

    class Meta:
        verbose_name = '材料推荐记录'
        verbose_name_plural = '材料推荐记录'
        ordering = ['-overall_score']
        unique_together = [['source_batch', 'recommended_batch']]

    def __str__(self):
        return f'{self.source_batch.batch_number} → {self.recommended_batch.batch_number} ({self.overall_score:.1f})'


class BowTypeMatching(models.Model):
    MATCH_LEVEL_EXCELLENT = 'excellent'
    MATCH_LEVEL_GOOD = 'good'
    MATCH_LEVEL_FAIR = 'fair'
    MATCH_LEVEL_POOR = 'poor'

    MATCH_LEVEL_CHOICES = [
        (MATCH_LEVEL_EXCELLENT, '极佳匹配'),
        (MATCH_LEVEL_GOOD, '良好匹配'),
        (MATCH_LEVEL_FAIR, '一般匹配'),
        (MATCH_LEVEL_POOR, '不推荐'),
    ]

    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='bow_type_matchings',
        verbose_name='材料批次'
    )
    bow_type = models.ForeignKey(
        BowType,
        on_delete=models.CASCADE,
        related_name='material_matchings',
        verbose_name='弓型'
    )
    match_level = models.CharField(
        max_length=20,
        choices=MATCH_LEVEL_CHOICES,
        verbose_name='匹配等级'
    )
    match_score = models.FloatField(
        verbose_name='匹配度评分(0-100)',
        help_text='材料与弓型的综合匹配度'
    )
    criteria_results = models.JSONField(
        default=dict,
        verbose_name='各项匹配标准结果'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='匹配说明'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='匹配时间'
    )

    class Meta:
        verbose_name = '弓型匹配记录'
        verbose_name_plural = '弓型匹配记录'
        ordering = ['-match_score']
        unique_together = [['batch', 'bow_type']]

    def __str__(self):
        return f'{self.batch.batch_number} ↔ {self.bow_type.name} ({self.match_score:.1f})'

    @property
    def match_color_class(self):
        mapping = {
            self.MATCH_LEVEL_EXCELLENT: 'badge-success',
            self.MATCH_LEVEL_GOOD: 'badge-info',
            self.MATCH_LEVEL_FAIR: 'badge-warning',
            self.MATCH_LEVEL_POOR: 'badge-danger',
        }
        return mapping.get(self.match_level, 'badge-gray')


class BatchRanking(models.Model):
    RANKING_TYPE_LIFETIME = 'lifetime'
    RANKING_TYPE_DURABILITY = 'durability'
    RANKING_TYPE_STABILITY = 'stability'
    RANKING_TYPE_PERFORMANCE = 'performance'
    RANKING_TYPE_OVERALL = 'overall'

    RANKING_TYPE_CHOICES = [
        (RANKING_TYPE_LIFETIME, '寿命排行'),
        (RANKING_TYPE_DURABILITY, '耐久性排行'),
        (RANKING_TYPE_STABILITY, '稳定性排行'),
        (RANKING_TYPE_PERFORMANCE, '性能排行'),
        (RANKING_TYPE_OVERALL, '综合排行'),
    ]

    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='rankings',
        verbose_name='材料批次'
    )
    ranking_type = models.CharField(
        max_length=20,
        choices=RANKING_TYPE_CHOICES,
        verbose_name='排行类型'
    )
    rank = models.IntegerField(
        verbose_name='排名'
    )
    score = models.FloatField(
        verbose_name='排行评分'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='排行时间'
    )

    class Meta:
        verbose_name = '批次排行记录'
        verbose_name_plural = '批次排行记录'
        ordering = ['ranking_type', 'rank']
        unique_together = [['ranking_type', 'batch']]

    def __str__(self):
        return f'#{self.rank} {self.batch.batch_number} - {self.get_ranking_type_display()}'


class ProcessRecipe(models.Model):
    RECIPE_TYPE_TRADITIONAL = 'traditional'
    RECIPE_TYPE_MODERN = 'modern'
    RECIPE_TYPE_HYBRID = 'hybrid'
    RECIPE_TYPE_EXPERIMENTAL = 'experimental'

    RECIPE_TYPE_CHOICES = [
        (RECIPE_TYPE_TRADITIONAL, '传统工艺'),
        (RECIPE_TYPE_MODERN, '现代工艺'),
        (RECIPE_TYPE_HYBRID, '混合工艺'),
        (RECIPE_TYPE_EXPERIMENTAL, '实验工艺'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_VALIDATED = 'validated'
    STATUS_APPROVED = 'approved'
    STATUS_OBSOLETE = 'obsolete'

    STATUS_CHOICES = [
        (STATUS_DRAFT, '草稿'),
        (STATUS_VALIDATED, '已验证'),
        (STATUS_APPROVED, '已批准'),
        (STATUS_OBSOLETE, '已废弃'),
    ]

    recipe_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='配方编号',
        help_text='工艺配方唯一编号'
    )
    recipe_name = models.CharField(
        max_length=200,
        verbose_name='配方名称'
    )
    recipe_type = models.CharField(
        max_length=30,
        choices=RECIPE_TYPE_CHOICES,
        default=RECIPE_TYPE_TRADITIONAL,
        verbose_name='配方类型'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name='配方状态'
    )
    target_bow_type = models.ForeignKey(
        BowType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recipes',
        verbose_name='目标弓型'
    )
    description = models.TextField(
        blank=True,
        verbose_name='配方说明'
    )
    base_material = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='基础材料',
        help_text='主要使用的材料，如蚕丝、麻、合成纤维等'
    )
    twist_direction = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='捻向',
        help_text='S捻或Z捻'
    )
    twist_count = models.FloatField(
        null=True,
        blank=True,
        verbose_name='捻度(捻/m)',
        help_text='每米捻回数'
    )
    strand_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='股数',
        help_text='弓弦的股线数量'
    )
    coating_material = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='涂层材料',
        help_text='如蜂蜡、树脂等'
    )
    curing_method = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='固化方式',
        help_text='如自然风干、加热固化等'
    )
    curing_temperature = models.FloatField(
        null=True,
        blank=True,
        verbose_name='固化温度(°C)'
    )
    curing_duration = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='固化时间(小时)'
    )
    pretreatment_process = models.TextField(
        blank=True,
        verbose_name='预处理工艺'
    )
    weaving_method = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='编织方式',
        help_text='如编织法、绞缠法等'
    )
    created_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='创建人'
    )
    approved_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='批准人'
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='批准时间'
    )
    version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name='版本号'
    )
    parent_recipe = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='derived_recipes',
        verbose_name='源配方'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '工艺配方'
        verbose_name_plural = '工艺配方'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipe_code} - {self.recipe_name}'

    def clean(self):
        if self.twist_count is not None and self.twist_count < 0:
            raise ValidationError({'twist_count': '捻度不能为负数'})
        if self.strand_count is not None and self.strand_count <= 0:
            raise ValidationError({'strand_count': '股数必须大于0'})
        if self.curing_temperature is not None and self.curing_temperature < -273:
            raise ValidationError({'curing_temperature': '温度不能低于绝对零度'})
        if self.curing_duration is not None and self.curing_duration < 0:
            raise ValidationError({'curing_duration': '固化时间不能为负数'})
        super().clean()

    @property
    def param_count(self):
        return self.params.count()

    @property
    def trial_count(self):
        return self.trials.count()

    @property
    def latest_prediction(self):
        return self.predictions.order_by('-predicted_at').first()

    def get_param_dict(self):
        return {
            p.param_name: {
                'value': p.param_value,
                'unit': p.param_unit,
                'type': p.param_type,
            }
            for p in self.params.all()
        }

    def get_performance_summary(self):
        results = TrialResult.objects.filter(trial_plan__recipe=self)
        if not results.exists():
            return None
        durabilities = list(results.filter(durability_score__isnull=False).values_list('durability_score', flat=True))
        stabilities = list(results.filter(stability_score__isnull=False).values_list('stability_score', flat=True))
        rebounds = list(results.filter(rebound_performance__isnull=False).values_list('rebound_performance', flat=True))
        return {
            'trial_count': results.count(),
            'avg_durability': round(sum(durabilities) / len(durabilities), 2) if durabilities else None,
            'avg_stability': round(sum(stabilities) / len(stabilities), 2) if stabilities else None,
            'avg_rebound': round(sum(rebounds) / len(rebounds), 2) if rebounds else None,
        }


class RecipeParam(models.Model):
    PARAM_TYPE_MATERIAL = 'material'
    PARAM_TYPE_PROCESS = 'process'
    PARAM_TYPE_ENVIRONMENT = 'environment'
    PARAM_TYPE_QUALITY = 'quality'

    PARAM_TYPE_CHOICES = [
        (PARAM_TYPE_MATERIAL, '材料属性'),
        (PARAM_TYPE_PROCESS, '工艺参数'),
        (PARAM_TYPE_ENVIRONMENT, '环境条件'),
        (PARAM_TYPE_QUALITY, '质量指标'),
    ]

    recipe = models.ForeignKey(
        ProcessRecipe,
        on_delete=models.CASCADE,
        related_name='params',
        verbose_name='所属配方'
    )
    param_name = models.CharField(
        max_length=100,
        verbose_name='参数名称'
    )
    param_value = models.FloatField(
        verbose_name='参数值'
    )
    param_unit = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='单位'
    )
    param_type = models.CharField(
        max_length=20,
        choices=PARAM_TYPE_CHOICES,
        default=PARAM_TYPE_PROCESS,
        verbose_name='参数类型'
    )
    min_value = models.FloatField(
        null=True,
        blank=True,
        verbose_name='最小值',
        help_text='参数允许的最小值'
    )
    max_value = models.FloatField(
        null=True,
        blank=True,
        verbose_name='最大值',
        help_text='参数允许的最大值'
    )
    is_critical = models.BooleanField(
        default=False,
        verbose_name='关键参数',
        help_text='是否为影响性能的关键参数'
    )
    description = models.TextField(
        blank=True,
        verbose_name='参数说明'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='记录时间'
    )

    class Meta:
        verbose_name = '配方工艺参数'
        verbose_name_plural = '配方工艺参数'
        ordering = ['param_type', 'param_name']
        unique_together = [['recipe', 'param_name']]

    def __str__(self):
        return f'{self.recipe.recipe_code} - {self.param_name}: {self.param_value}{self.param_unit}'

    def clean(self):
        if self.param_value is None:
            raise ValidationError({'param_value': '参数值不能为空'})
        if self.min_value is not None and self.param_value < self.min_value:
            raise ValidationError({'param_value': f'参数值不能小于最小值{self.min_value}'})
        if self.max_value is not None and self.param_value > self.max_value:
            raise ValidationError({'param_value': f'参数值不能大于最大值{self.max_value}'})
        super().clean()

    @property
    def tolerance_range(self):
        if self.min_value is not None and self.max_value is not None:
            return self.max_value - self.min_value
        return None


class PerformanceTarget(models.Model):
    recipe = models.ForeignKey(
        ProcessRecipe,
        on_delete=models.CASCADE,
        related_name='performance_targets',
        verbose_name='所属配方'
    )
    target_name = models.CharField(
        max_length=100,
        verbose_name='目标名称'
    )
    target_category = models.CharField(
        max_length=50,
        choices=[
            ('durability', '耐久性'),
            ('stability', '稳定性'),
            ('rebound', '回弹表现'),
            ('strength', '强度'),
            ('lifespan', '使用寿命'),
            ('risk', '风险等级'),
            ('other', '其他'),
        ],
        default='durability',
        verbose_name='目标类别'
    )
    target_value = models.FloatField(
        verbose_name='目标值'
    )
    target_unit = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='单位'
    )
    comparison_type = models.CharField(
        max_length=20,
        choices=[
            ('>=', '大于等于'),
            ('<=', '小于等于'),
            ('=', '等于'),
            ('>', '大于'),
            ('<', '小于'),
            ('range', '范围内'),
        ],
        default='>=',
        verbose_name='比较方式'
    )
    min_target = models.FloatField(
        null=True,
        blank=True,
        verbose_name='最小目标值'
    )
    max_target = models.FloatField(
        null=True,
        blank=True,
        verbose_name='最大目标值'
    )
    priority = models.IntegerField(
        default=1,
        verbose_name='优先级',
        help_text='数字越小优先级越高'
    )
    is_mandatory = models.BooleanField(
        default=True,
        verbose_name='必须达成',
        help_text='是否为必须达成的关键目标'
    )
    description = models.TextField(
        blank=True,
        verbose_name='目标说明'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '性能目标'
        verbose_name_plural = '性能目标'
        ordering = ['priority', 'target_category']

    def __str__(self):
        return f'{self.recipe.recipe_code} - {self.target_name}: {self.comparison_type}{self.target_value}{self.target_unit}'

    def clean(self):
        if self.comparison_type == 'range':
            if self.min_target is None or self.max_target is None:
                raise ValidationError('选择"范围内"时必须填写最小和最大目标值')
            if self.min_target > self.max_target:
                raise ValidationError({'min_target': '最小目标值不能大于最大目标值'})
        super().clean()

    def evaluate(self, actual_value):
        if actual_value is None:
            return None
        if self.comparison_type == '>=':
            return actual_value >= self.target_value
        elif self.comparison_type == '<=':
            return actual_value <= self.target_value
        elif self.comparison_type == '=':
            return abs(actual_value - self.target_value) < 0.001
        elif self.comparison_type == '>':
            return actual_value > self.target_value
        elif self.comparison_type == '<':
            return actual_value < self.target_value
        elif self.comparison_type == 'range':
            return self.min_target <= actual_value <= self.max_target
        return None


class TrialPlan(models.Model):
    PLAN_STATUS_PLANNING = 'planning'
    PLAN_STATUS_IN_PROGRESS = 'in_progress'
    PLAN_STATUS_COMPLETED = 'completed'
    PLAN_STATUS_CANCELLED = 'cancelled'
    PLAN_STATUS_FAILED = 'failed'

    PLAN_STATUS_CHOICES = [
        (PLAN_STATUS_PLANNING, '规划中'),
        (PLAN_STATUS_IN_PROGRESS, '进行中'),
        (PLAN_STATUS_COMPLETED, '已完成'),
        (PLAN_STATUS_CANCELLED, '已取消'),
        (PLAN_STATUS_FAILED, '试制失败'),
    ]

    TRIAL_TYPE_BENCH = 'bench'
    TRIAL_TYPE_FIELD = 'field'
    TRIAL_TYPE_FULL = 'full'

    TRIAL_TYPE_CHOICES = [
        (TRIAL_TYPE_BENCH, '台架测试'),
        (TRIAL_TYPE_FIELD, '现场测试'),
        (TRIAL_TYPE_FULL, '完整试制'),
    ]

    plan_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='试制编号'
    )
    plan_name = models.CharField(
        max_length=200,
        verbose_name='试制方案名称'
    )
    recipe = models.ForeignKey(
        ProcessRecipe,
        on_delete=models.CASCADE,
        related_name='trials',
        verbose_name='关联配方'
    )
    material_batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trial_plans',
        verbose_name='关联材料批次'
    )
    trial_type = models.CharField(
        max_length=20,
        choices=TRIAL_TYPE_CHOICES,
        default=TRIAL_TYPE_BENCH,
        verbose_name='试制类型'
    )
    status = models.CharField(
        max_length=20,
        choices=PLAN_STATUS_CHOICES,
        default=PLAN_STATUS_PLANNING,
        verbose_name='试制状态'
    )
    target_bow_type = models.ForeignKey(
        BowType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trial_plans',
        verbose_name='测试弓型'
    )
    sample_count = models.IntegerField(
        default=1,
        verbose_name='试样数量',
        help_text='本次试制的试样数量'
    )
    planned_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='计划开始日期'
    )
    planned_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='计划完成日期'
    )
    actual_start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='实际开始日期'
    )
    actual_end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='实际完成日期'
    )
    tester = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='试制人员'
    )
    test_environment = models.TextField(
        blank=True,
        verbose_name='测试环境',
        help_text='温度、湿度等环境条件描述'
    )
    preparation_notes = models.TextField(
        blank=True,
        verbose_name='准备工作说明'
    )
    test_procedure = models.TextField(
        blank=True,
        verbose_name='测试步骤'
    )
    expected_outcomes = models.TextField(
        blank=True,
        verbose_name='预期结果'
    )
    created_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '试制方案'
        verbose_name_plural = '试制方案'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.plan_code} - {self.plan_name}'

    def clean(self):
        if self.sample_count is not None and self.sample_count <= 0:
            raise ValidationError({'sample_count': '试样数量必须大于0'})
        if self.planned_start_date and self.planned_end_date:
            if self.planned_start_date > self.planned_end_date:
                raise ValidationError({'planned_start_date': '计划开始日期不能晚于计划完成日期'})
        if self.actual_start_date and self.actual_end_date:
            if self.actual_start_date > self.actual_end_date:
                raise ValidationError({'actual_start_date': '实际开始日期不能晚于实际完成日期'})
        super().clean()

    @property
    def result_count(self):
        return self.results.count()

    @property
    def latest_result(self):
        return self.results.order_by('-test_date').first()

    @property
    def duration_days(self):
        if self.actual_start_date and self.actual_end_date:
            return (self.actual_end_date - self.actual_start_date).days
        if self.planned_start_date and self.planned_end_date:
            return (self.planned_end_date - self.planned_start_date).days
        return None

    def start(self):
        self.status = self.PLAN_STATUS_IN_PROGRESS
        self.actual_start_date = timezone.now().date()
        self.save()

    def complete(self):
        self.status = self.PLAN_STATUS_COMPLETED
        self.actual_end_date = timezone.now().date()
        self.save()


class TrialResult(models.Model):
    RISK_LEVEL_LOW = 'low'
    RISK_LEVEL_MEDIUM = 'medium'
    RISK_LEVEL_HIGH = 'high'
    RISK_LEVEL_CRITICAL = 'critical'

    RISK_LEVEL_CHOICES = [
        (RISK_LEVEL_LOW, '低风险'),
        (RISK_LEVEL_MEDIUM, '中风险'),
        (RISK_LEVEL_HIGH, '高风险'),
        (RISK_LEVEL_CRITICAL, '极高风险'),
    ]

    RESULT_PASS = 'pass'
    RESULT_PARTIAL = 'partial'
    RESULT_FAIL = 'fail'
    RESULT_PENDING = 'pending'

    RESULT_CHOICES = [
        (RESULT_PASS, '全部通过'),
        (RESULT_PARTIAL, '部分通过'),
        (RESULT_FAIL, '未通过'),
        (RESULT_PENDING, '待评估'),
    ]

    trial_plan = models.ForeignKey(
        TrialPlan,
        on_delete=models.CASCADE,
        related_name='results',
        verbose_name='所属试制方案'
    )
    sample_id = models.CharField(
        max_length=50,
        verbose_name='试样编号'
    )
    test_date = models.DateField(
        default=timezone.now,
        verbose_name='测试日期'
    )
    test_operator = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='测试人员'
    )

    durability_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='耐久性评分(0-100)',
        help_text='基于疲劳和拉伸测试的耐久性综合评分'
    )
    stability_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='稳定性评分(0-100)',
        help_text='基于数据一致性和回弹稳定性的评分'
    )
    rebound_performance = models.FloatField(
        null=True,
        blank=True,
        verbose_name='回弹表现评分(0-100)',
        help_text='回弹率和回弹速度综合评分'
    )
    strength_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='强度评分(0-100)',
        help_text='抗拉强度和断裂强度评分'
    )
    overall_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='综合评分(0-100)'
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default=RISK_LEVEL_LOW,
        verbose_name='风险等级'
    )
    risk_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='风险指数(0-100)',
        help_text='越高风险越大'
    )

    measured_force = models.FloatField(
        null=True,
        blank=True,
        verbose_name='实测最大拉力(N)'
    )
    measured_elongation = models.FloatField(
        null=True,
        blank=True,
        verbose_name='实测断裂伸长量(mm)'
    )
    measured_rebound_rate = models.FloatField(
        null=True,
        blank=True,
        verbose_name='实测回弹率(%)'
    )
    fatigue_cycles = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='疲劳循环次数'
    )
    measured_diameter = models.FloatField(
        null=True,
        blank=True,
        verbose_name='实测直径(mm)'
    )
    weight_per_meter = models.FloatField(
        null=True,
        blank=True,
        verbose_name='每米重量(g/m)'
    )

    lifespan_estimate_hours = models.FloatField(
        null=True,
        blank=True,
        verbose_name='预估寿命(小时)'
    )
    estimated_shots = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='预估射箭次数'
    )

    result_status = models.CharField(
        max_length=20,
        choices=RESULT_CHOICES,
        default=RESULT_PENDING,
        verbose_name='目标达成情况'
    )
    targets_met = models.JSONField(
        default=list,
        verbose_name='达成的目标列表'
    )
    targets_missed = models.JSONField(
        default=list,
        verbose_name='未达成的目标列表'
    )

    is_broken = models.BooleanField(
        default=False,
        verbose_name='是否断裂'
    )
    break_location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='断裂位置'
    )
    break_mode = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='断裂模式',
        help_text='如脆性断裂、韧性断裂等'
    )
    break_reason = models.TextField(
        blank=True,
        verbose_name='断裂原因分析'
    )

    observations = models.TextField(
        blank=True,
        verbose_name='测试观察'
    )
    issues_found = models.TextField(
        blank=True,
        verbose_name='发现的问题'
    )
    recommendations = models.TextField(
        blank=True,
        verbose_name='改进建议'
    )
    raw_data_reference = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='原始数据引用'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='备注'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='记录时间'
    )

    class Meta:
        verbose_name = '试制结果'
        verbose_name_plural = '试制结果'
        ordering = ['-test_date']
        unique_together = [['trial_plan', 'sample_id']]

    def __str__(self):
        return f'{self.trial_plan.plan_code} - {self.sample_id}'

    def clean(self):
        for field_name in ['durability_score', 'stability_score', 'rebound_performance', 'strength_score', 'overall_score', 'risk_score']:
            value = getattr(self, field_name)
            if value is not None and (value < 0 or value > 100):
                raise ValidationError({field_name: '评分必须在0-100之间'})
        for field_name in ['measured_force', 'measured_elongation', 'fatigue_cycles', 'measured_diameter', 'weight_per_meter']:
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValidationError({field_name: '测量值不能为负数'})
        if self.measured_rebound_rate is not None and (self.measured_rebound_rate < 0 or self.measured_rebound_rate > 100):
            raise ValidationError({'measured_rebound_rate': '回弹率必须在0-100之间'})
        super().clean()

    def save(self, *args, **kwargs):
        if self.overall_score is None:
            scores = []
            for s in [self.durability_score, self.stability_score, self.rebound_performance, self.strength_score]:
                if s is not None:
                    scores.append(s)
            if scores:
                self.overall_score = round(sum(scores) / len(scores), 2)

        if self.risk_score is None and self.risk_level:
            risk_mapping = {
                self.RISK_LEVEL_LOW: 20,
                self.RISK_LEVEL_MEDIUM: 50,
                self.RISK_LEVEL_HIGH: 75,
                self.RISK_LEVEL_CRITICAL: 95,
            }
            self.risk_score = risk_mapping.get(self.risk_level, 50)
        elif self.risk_score is not None and not self.risk_level:
            if self.risk_score < 30:
                self.risk_level = self.RISK_LEVEL_LOW
            elif self.risk_score < 60:
                self.risk_level = self.RISK_LEVEL_MEDIUM
            elif self.risk_score < 85:
                self.risk_level = self.RISK_LEVEL_HIGH
            else:
                self.risk_level = self.RISK_LEVEL_CRITICAL

        super().save(*args, **kwargs)

    def evaluate_targets(self):
        recipe = self.trial_plan.recipe
        targets = recipe.performance_targets.all()
        met = []
        missed = []

        value_mapping = {
            'durability': self.durability_score,
            'stability': self.stability_score,
            'rebound': self.rebound_performance,
            'strength': self.strength_score,
            'lifespan': self.lifespan_estimate_hours,
        }

        for target in targets:
            actual_value = value_mapping.get(target.target_category)
            if actual_value is not None:
                result = target.evaluate(actual_value)
                target_info = {
                    'id': target.id,
                    'name': target.target_name,
                    'category': target.target_category,
                    'target': target.target_value,
                    'unit': target.target_unit,
                    'actual': actual_value,
                    'mandatory': target.is_mandatory,
                }
                if result:
                    met.append(target_info)
                else:
                    missed.append(target_info)

        self.targets_met = met
        self.targets_missed = missed

        mandatory_missed = [t for t in missed if t.get('mandatory')]
        if not missed:
            self.result_status = self.RESULT_PASS
        elif not mandatory_missed:
            self.result_status = self.RESULT_PARTIAL
        else:
            self.result_status = self.RESULT_FAIL

        return met, missed

    @property
    def risk_color_class(self):
        mapping = {
            self.RISK_LEVEL_LOW: 'badge-success',
            self.RISK_LEVEL_MEDIUM: 'badge-warning',
            self.RISK_LEVEL_HIGH: 'badge-danger',
            self.RISK_LEVEL_CRITICAL: 'badge-danger',
        }
        return mapping.get(self.risk_level, 'badge-gray')

    @property
    def result_color_class(self):
        mapping = {
            self.RESULT_PASS: 'badge-success',
            self.RESULT_PARTIAL: 'badge-info',
            self.RESULT_FAIL: 'badge-danger',
            self.RESULT_PENDING: 'badge-secondary',
        }
        return mapping.get(self.result_status, 'badge-gray')

    def get_performance_dict(self):
        return {
            'durability': self.durability_score,
            'stability': self.stability_score,
            'rebound': self.rebound_performance,
            'strength': self.strength_score,
            'overall': self.overall_score,
            'risk_level': self.risk_level,
            'risk_score': self.risk_score,
        }


class RecipePrediction(models.Model):
    RISK_LEVEL_LOW = 'low'
    RISK_LEVEL_MEDIUM = 'medium'
    RISK_LEVEL_HIGH = 'high'
    RISK_LEVEL_CRITICAL = 'critical'

    RISK_LEVEL_CHOICES = [
        (RISK_LEVEL_LOW, '低风险'),
        (RISK_LEVEL_MEDIUM, '中风险'),
        (RISK_LEVEL_HIGH, '高风险'),
        (RISK_LEVEL_CRITICAL, '极高风险'),
    ]

    recipe = models.ForeignKey(
        ProcessRecipe,
        on_delete=models.CASCADE,
        related_name='predictions',
        verbose_name='所属配方'
    )
    predicted_durability = models.FloatField(
        verbose_name='预测耐久性评分(0-100)'
    )
    predicted_stability = models.FloatField(
        verbose_name='预测稳定性评分(0-100)'
    )
    predicted_rebound = models.FloatField(
        verbose_name='预测回弹表现(0-100)'
    )
    predicted_strength = models.FloatField(
        null=True,
        blank=True,
        verbose_name='预测强度评分(0-100)'
    )
    predicted_overall = models.FloatField(
        verbose_name='预测综合评分(0-100)'
    )
    predicted_risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        verbose_name='预测风险等级'
    )
    predicted_risk_score = models.FloatField(
        verbose_name='预测风险指数(0-100)'
    )
    predicted_lifespan_hours = models.FloatField(
        null=True,
        blank=True,
        verbose_name='预测寿命(小时)'
    )
    confidence_level = models.FloatField(
        default=0.7,
        verbose_name='置信度(0-1)',
        help_text='预测结果的置信度'
    )
    key_factors = models.JSONField(
        default=list,
        verbose_name='关键影响因素'
    )
    strength_analysis = models.JSONField(
        default=list,
        verbose_name='优势分析'
    )
    weakness_analysis = models.JSONField(
        default=list,
        verbose_name='劣势分析'
    )
    optimization_suggestions = models.JSONField(
        default=list,
        verbose_name='优化建议'
    )
    prediction_method = models.CharField(
        max_length=100,
        default='rule_based',
        verbose_name='预测方法'
    )
    reference_trials = models.JSONField(
        default=list,
        verbose_name='参考试制记录'
    )
    predicted_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='预测时间'
    )
    is_latest = models.BooleanField(
        default=True,
        verbose_name='是否为最新预测'
    )

    class Meta:
        verbose_name = '配方性能预测'
        verbose_name_plural = '配方性能预测'
        ordering = ['-predicted_at']

    def __str__(self):
        return f'{self.recipe.recipe_code} - 综合:{self.predicted_overall:.1f} - {self.get_predicted_risk_level_display()}'

    def save(self, *args, **kwargs):
        if self.is_latest:
            RecipePrediction.objects.filter(
                recipe=self.recipe,
                is_latest=True
            ).exclude(pk=self.pk).update(is_latest=False)
        super().save(*args, **kwargs)

    def clean(self):
        for field in ['predicted_durability', 'predicted_stability', 'predicted_rebound',
                      'predicted_strength', 'predicted_overall', 'predicted_risk_score']:
            value = getattr(self, field)
            if value is not None and (value < 0 or value > 100):
                raise ValidationError({field: '预测评分必须在0-100之间'})
        if self.confidence_level < 0 or self.confidence_level > 1:
            raise ValidationError({'confidence_level': '置信度必须在0-1之间'})
        super().clean()

    @property
    def risk_color_class(self):
        mapping = {
            self.RISK_LEVEL_LOW: 'badge-success',
            self.RISK_LEVEL_MEDIUM: 'badge-warning',
            self.RISK_LEVEL_HIGH: 'badge-danger',
            self.RISK_LEVEL_CRITICAL: 'badge-danger',
        }
        return mapping.get(self.predicted_risk_level, 'badge-gray')

    def get_prediction_dict(self):
        return {
            'durability': self.predicted_durability,
            'stability': self.predicted_stability,
            'rebound': self.predicted_rebound,
            'strength': self.predicted_strength,
            'overall': self.predicted_overall,
            'risk_level': self.predicted_risk_level,
            'risk_score': self.predicted_risk_score,
            'lifespan_hours': self.predicted_lifespan_hours,
            'confidence': self.confidence_level,
        }


class RecipeComparison(models.Model):
    COMPARISON_TYPE_PERFORMANCE = 'performance'
    COMPARISON_TYPE_PARAMS = 'params'
    COMPARISON_TYPE_FULL = 'full'

    COMPARISON_TYPE_CHOICES = [
        (COMPARISON_TYPE_PERFORMANCE, '性能对比'),
        (COMPARISON_TYPE_PARAMS, '参数对比'),
        (COMPARISON_TYPE_FULL, '综合对比'),
    ]

    name = models.CharField(
        max_length=200,
        verbose_name='对比名称'
    )
    comparison_type = models.CharField(
        max_length=30,
        choices=COMPARISON_TYPE_CHOICES,
        default=COMPARISON_TYPE_FULL,
        verbose_name='对比类型'
    )
    recipes = models.ManyToManyField(
        ProcessRecipe,
        related_name='comparisons',
        verbose_name='参与对比的配方'
    )
    metrics = models.JSONField(
        default=list,
        verbose_name='对比指标列表'
    )
    reference_recipe_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='参照配方ID'
    )
    visualization_config = models.JSONField(
        default=dict,
        verbose_name='可视化配置'
    )
    created_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='创建人'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '配方对比分析'
        verbose_name_plural = '配方对比分析'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_comparison_type_display()})'

    @property
    def recipe_count(self):
        return self.recipes.count()

    def generate_comparison_data(self):
        recipes = self.recipes.all()
        data = {
            'recipes': [],
            'metrics_summary': {},
        }

        for recipe in recipes:
            recipe_data = {
                'id': recipe.id,
                'code': recipe.recipe_code,
                'name': recipe.recipe_name,
                'type': recipe.get_recipe_type_display(),
                'status': recipe.get_status_display(),
                'params': recipe.get_param_dict(),
            }

            prediction = recipe.latest_prediction
            if prediction:
                recipe_data['prediction'] = prediction.get_prediction_dict()

            performance = recipe.get_performance_summary()
            if performance:
                recipe_data['actual_performance'] = performance

            data['recipes'].append(recipe_data)

        return data


class OptimizationSuggestion(models.Model):
    SEVERITY_LOW = 'low'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_HIGH = 'high'
    SEVERITY_CRITICAL = 'critical'

    SEVERITY_CHOICES = [
        (SEVERITY_LOW, '低'),
        (SEVERITY_MEDIUM, '中'),
        (SEVERITY_HIGH, '高'),
        (SEVERITY_CRITICAL, '关键'),
    ]

    CATEGORY_PARAMETER = 'parameter'
    CATEGORY_MATERIAL = 'material'
    CATEGORY_PROCESS = 'process'
    CATEGORY_TESTING = 'testing'
    CATEGORY_OTHER = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_PARAMETER, '参数调整'),
        (CATEGORY_MATERIAL, '材料更换'),
        (CATEGORY_PROCESS, '工艺改进'),
        (CATEGORY_TESTING, '测试优化'),
        (CATEGORY_OTHER, '其他'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_IMPLEMENTED = 'implemented'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待处理'),
        (STATUS_ACCEPTED, '已采纳'),
        (STATUS_REJECTED, '已拒绝'),
        (STATUS_IMPLEMENTED, '已实施'),
    ]

    recipe = models.ForeignKey(
        ProcessRecipe,
        on_delete=models.CASCADE,
        related_name='suggestions',
        verbose_name='所属配方'
    )
    trial_result = models.ForeignKey(
        TrialResult,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suggestions',
        verbose_name='关联试制结果'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='建议标题'
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_PARAMETER,
        verbose_name='建议类别'
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_MEDIUM,
        verbose_name='重要程度'
    )
    description = models.TextField(
        verbose_name='建议详情'
    )
    current_state = models.TextField(
        blank=True,
        verbose_name='当前状态描述'
    )
    suggested_action = models.TextField(
        blank=True,
        verbose_name='建议操作'
    )
    expected_improvement = models.JSONField(
        default=dict,
        verbose_name='预期改善效果',
        help_text='如 {"durability": 10, "stability": 5} 表示各指标预期提升百分比'
    )
    affected_params = models.JSONField(
        default=list,
        verbose_name='受影响的参数'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='处理状态'
    )
    reviewer_notes = models.TextField(
        blank=True,
        verbose_name='审核备注'
    )
    reviewed_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='审核人'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='审核时间'
    )
    generated_by = models.CharField(
        max_length=100,
        default='system',
        verbose_name='生成者'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '优化建议'
        verbose_name_plural = '优化建议'
        ordering = ['-severity', '-created_at']

    def __str__(self):
        return f'{self.recipe.recipe_code} - {self.title}'

    @property
    def severity_color_class(self):
        mapping = {
            self.SEVERITY_LOW: 'badge-info',
            self.SEVERITY_MEDIUM: 'badge-warning',
            self.SEVERITY_HIGH: 'badge-danger',
            self.SEVERITY_CRITICAL: 'badge-danger',
        }
        return mapping.get(self.severity, 'badge-gray')

    @property
    def status_color_class(self):
        mapping = {
            self.STATUS_PENDING: 'badge-secondary',
            self.STATUS_ACCEPTED: 'badge-info',
            self.STATUS_REJECTED: 'badge-light',
            self.STATUS_IMPLEMENTED: 'badge-success',
        }
        return mapping.get(self.status, 'badge-gray')

    def accept(self, reviewer='', notes=''):
        self.status = self.STATUS_ACCEPTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.reviewer_notes = notes
        self.save()

    def reject(self, reviewer='', notes=''):
        self.status = self.STATUS_REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.reviewer_notes = notes
        self.save()

    def mark_implemented(self, reviewer='', notes=''):
        self.status = self.STATUS_IMPLEMENTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        if notes:
            self.reviewer_notes = notes
        self.save()


class DefectType(models.Model):
    CATEGORY_MATERIAL = 'material'
    CATEGORY_PROCESS = 'process'
    CATEGORY_STRUCTURE = 'structure'
    CATEGORY_SURFACE = 'surface'
    CATEGORY_OTHER = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_MATERIAL, '材料缺陷'),
        (CATEGORY_PROCESS, '工艺缺陷'),
        (CATEGORY_STRUCTURE, '结构缺陷'),
        (CATEGORY_SURFACE, '表面缺陷'),
        (CATEGORY_OTHER, '其他缺陷'),
    ]

    SEVERITY_LOW = 'low'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_HIGH = 'high'
    SEVERITY_CRITICAL = 'critical'

    SEVERITY_CHOICES = [
        (SEVERITY_LOW, '轻微'),
        (SEVERITY_MEDIUM, '中等'),
        (SEVERITY_HIGH, '严重'),
        (SEVERITY_CRITICAL, '致命'),
    ]

    defect_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='缺陷编码'
    )
    defect_name = models.CharField(
        max_length=200,
        verbose_name='缺陷名称'
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER,
        verbose_name='缺陷类别'
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_MEDIUM,
        verbose_name='严重程度'
    )
    description = models.TextField(
        blank=True,
        verbose_name='缺陷描述'
    )
    typical_causes = models.TextField(
        blank=True,
        verbose_name='典型原因'
    )
    detection_method = models.TextField(
        blank=True,
        verbose_name='检测方法'
    )
    prevention_measures = models.TextField(
        blank=True,
        verbose_name='预防措施'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '缺陷类型'
        verbose_name_plural = '缺陷类型'
        ordering = ['category', 'severity', 'defect_code']

    def __str__(self):
        return f'{self.defect_code} - {self.defect_name}'

    @property
    def severity_color_class(self):
        mapping = {
            self.SEVERITY_LOW: 'badge-info',
            self.SEVERITY_MEDIUM: 'badge-warning',
            self.SEVERITY_HIGH: 'badge-danger',
            self.SEVERITY_CRITICAL: 'badge-danger',
        }
        return mapping.get(self.severity, 'badge-gray')

    @property
    def record_count(self):
        return self.defect_records.count()


class DefectRecord(models.Model):
    SOURCE_TENSION_TEST = 'tension'
    SOURCE_FATIGUE_TEST = 'fatigue'
    SOURCE_TRIAL = 'trial'
    SOURCE_INSPECTION = 'inspection'
    SOURCE_OTHER = 'other'

    SOURCE_CHOICES = [
        (SOURCE_TENSION_TEST, '拉伸测试'),
        (SOURCE_FATIGUE_TEST, '疲劳测试'),
        (SOURCE_TRIAL, '试制发现'),
        (SOURCE_INSPECTION, '质检发现'),
        (SOURCE_OTHER, '其他来源'),
    ]

    STATUS_DETECTED = 'detected'
    STATUS_ANALYZING = 'analyzing'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_DETECTED, '已发现'),
        (STATUS_ANALYZING, '分析中'),
        (STATUS_RESOLVED, '已解决'),
        (STATUS_CLOSED, '已关闭'),
    ]

    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='defect_records',
        verbose_name='材料批次'
    )
    defect_type = models.ForeignKey(
        DefectType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='defect_records',
        verbose_name='缺陷类型'
    )
    defect_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='缺陷记录编号'
    )
    source_type = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default=SOURCE_INSPECTION,
        verbose_name='发现来源'
    )
    source_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='来源记录ID'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DETECTED,
        verbose_name='处理状态'
    )
    defect_location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='缺陷位置'
    )
    defect_size = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='缺陷尺寸'
    )
    description = models.TextField(
        verbose_name='缺陷描述'
    )
    severity_assessment = models.CharField(
        max_length=20,
        choices=DefectType.SEVERITY_CHOICES,
        default=DefectType.SEVERITY_MEDIUM,
        verbose_name='严重程度评估'
    )
    root_cause = models.TextField(
        blank=True,
        verbose_name='根本原因分析'
    )
    corrective_action = models.TextField(
        blank=True,
        verbose_name='纠正措施'
    )
    preventive_action = models.TextField(
        blank=True,
        verbose_name='预防措施'
    )
    detected_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='发现人'
    )
    detected_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='发现时间'
    )
    resolved_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='处理人'
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='解决时间'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='备注'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '缺陷记录'
        verbose_name_plural = '缺陷记录'
        ordering = ['-detected_at']

    def __str__(self):
        return f'{self.defect_code} - {self.batch.batch_number}'

    @property
    def status_color_class(self):
        mapping = {
            self.STATUS_DETECTED: 'badge-danger',
            self.STATUS_ANALYZING: 'badge-warning',
            self.STATUS_RESOLVED: 'badge-info',
            self.STATUS_CLOSED: 'badge-success',
        }
        return mapping.get(self.status, 'badge-gray')

    @property
    def severity_color_class(self):
        mapping = {
            DefectType.SEVERITY_LOW: 'badge-info',
            DefectType.SEVERITY_MEDIUM: 'badge-warning',
            DefectType.SEVERITY_HIGH: 'badge-danger',
            DefectType.SEVERITY_CRITICAL: 'badge-danger',
        }
        return mapping.get(self.severity_assessment, 'badge-gray')

    def resolve(self, resolver='', corrective='', preventive='', notes=''):
        self.status = self.STATUS_RESOLVED
        self.resolved_by = resolver
        self.resolved_at = timezone.now()
        if corrective:
            self.corrective_action = corrective
        if preventive:
            self.preventive_action = preventive
        if notes:
            self.notes = notes
        self.save()

    def close(self):
        self.status = self.STATUS_CLOSED
        self.save()


class FractureDiagnosis(models.Model):
    DIAGNOSIS_STATUS_PENDING = 'pending'
    DIAGNOSIS_STATUS_IN_PROGRESS = 'in_progress'
    DIAGNOSIS_STATUS_COMPLETED = 'completed'

    DIAGNOSIS_STATUS_CHOICES = [
        (DIAGNOSIS_STATUS_PENDING, '待诊断'),
        (DIAGNOSIS_STATUS_IN_PROGRESS, '诊断中'),
        (DIAGNOSIS_STATUS_COMPLETED, '已完成'),
    ]

    FRACTURE_MODE_DUCTILE = 'ductile'
    FRACTURE_MODE_BRITTLE = 'brittle'
    FRACTURE_MODE_FATIGUE = 'fatigue'
    FRACTURE_MODE_CREEP = 'creep'
    FRACTURE_MODE_OTHER = 'other'

    FRACTURE_MODE_CHOICES = [
        (FRACTURE_MODE_DUCTILE, '韧性断裂'),
        (FRACTURE_MODE_BRITTLE, '脆性断裂'),
        (FRACTURE_MODE_FATIGUE, '疲劳断裂'),
        (FRACTURE_MODE_CREEP, '蠕变断裂'),
        (FRACTURE_MODE_OTHER, '其他'),
    ]

    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='fracture_diagnoses',
        verbose_name='材料批次'
    )
    diagnosis_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='诊断编号'
    )
    source_test_type = models.CharField(
        max_length=20,
        choices=[
            ('tension', '拉伸测试'),
            ('fatigue', '疲劳测试'),
            ('trial', '试制测试'),
        ],
        default='tension',
        verbose_name='断裂测试类型'
    )
    source_test_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='测试记录ID'
    )
    diagnosis_status = models.CharField(
        max_length=20,
        choices=DIAGNOSIS_STATUS_CHOICES,
        default=DIAGNOSIS_STATUS_PENDING,
        verbose_name='诊断状态'
    )
    fracture_mode = models.CharField(
        max_length=30,
        choices=FRACTURE_MODE_CHOICES,
        default=FRACTURE_MODE_OTHER,
        verbose_name='断裂模式'
    )
    fracture_location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='断裂位置'
    )
    fracture_surface = models.TextField(
        blank=True,
        verbose_name='断口形貌描述'
    )
    primary_cause = models.TextField(
        blank=True,
        verbose_name='主要原因'
    )
    secondary_causes = models.JSONField(
        default=list,
        verbose_name='次要原因列表'
    )
    root_cause_category = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='根本原因类别'
    )
    material_factors = models.JSONField(
        default=list,
        verbose_name='材料因素'
    )
    process_factors = models.JSONField(
        default=list,
        verbose_name='工艺因素'
    )
    environmental_factors = models.JSONField(
        default=list,
        verbose_name='环境因素'
    )
    test_factors = models.JSONField(
        default=list,
        verbose_name='测试因素'
    )
    fracture_energy = models.FloatField(
        null=True,
        blank=True,
        verbose_name='断裂能(J)'
    )
    crack_propagation_rate = models.FloatField(
        null=True,
        blank=True,
        verbose_name='裂纹扩展速率'
    )
    fatigue_crack_initiation_cycles = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='疲劳裂纹萌生循环数'
    )
    diagnosis_conclusion = models.TextField(
        blank=True,
        verbose_name='诊断结论'
    )
    improvement_suggestions = models.TextField(
        blank=True,
        verbose_name='改进建议'
    )
    diagnosed_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='诊断人'
    )
    diagnosed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='诊断完成时间'
    )
    reviewed_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='审核人'
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name='是否验证'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='备注'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '断裂诊断记录'
        verbose_name_plural = '断裂诊断记录'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.diagnosis_code} - {self.batch.batch_number}'

    @property
    def status_color_class(self):
        mapping = {
            self.DIAGNOSIS_STATUS_PENDING: 'badge-secondary',
            self.DIAGNOSIS_STATUS_IN_PROGRESS: 'badge-warning',
            self.DIAGNOSIS_STATUS_COMPLETED: 'badge-success',
        }
        return mapping.get(self.diagnosis_status, 'badge-gray')

    def start_diagnosis(self, diagnosed_by=''):
        self.diagnosis_status = self.DIAGNOSIS_STATUS_IN_PROGRESS
        if diagnosed_by:
            self.diagnosed_by = diagnosed_by
        self.save()

    def complete_diagnosis(self, **kwargs):
        self.diagnosis_status = self.DIAGNOSIS_STATUS_COMPLETED
        self.diagnosed_at = timezone.now()
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()


class QualityIssue(models.Model):
    ISSUE_TYPE_DEFECT = 'defect'
    ISSUE_TYPE_PERFORMANCE = 'performance'
    ISSUE_TYPE_PROCESS = 'process'
    ISSUE_TYPE_MATERIAL = 'material'
    ISSUE_TYPE_OTHER = 'other'

    ISSUE_TYPE_CHOICES = [
        (ISSUE_TYPE_DEFECT, '缺陷问题'),
        (ISSUE_TYPE_PERFORMANCE, '性能问题'),
        (ISSUE_TYPE_PROCESS, '工艺问题'),
        (ISSUE_TYPE_MATERIAL, '材料问题'),
        (ISSUE_TYPE_OTHER, '其他问题'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CRITICAL = 'critical'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, '低'),
        (PRIORITY_MEDIUM, '中'),
        (PRIORITY_HIGH, '高'),
        (PRIORITY_CRITICAL, '紧急'),
    ]

    STATUS_OPEN = 'open'
    STATUS_INVESTIGATING = 'investigating'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_OPEN, '已立项'),
        (STATUS_INVESTIGATING, '调查中'),
        (STATUS_RESOLVED, '已解决'),
        (STATUS_CLOSED, '已关闭'),
    ]

    issue_code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='问题编号'
    )
    issue_title = models.CharField(
        max_length=200,
        verbose_name='问题标题'
    )
    issue_type = models.CharField(
        max_length=30,
        choices=ISSUE_TYPE_CHOICES,
        default=ISSUE_TYPE_OTHER,
        verbose_name='问题类型'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        verbose_name='优先级'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
        verbose_name='处理状态'
    )
    description = models.TextField(
        verbose_name='问题描述'
    )
    impact_analysis = models.TextField(
        blank=True,
        verbose_name='影响分析'
    )
    root_cause = models.TextField(
        blank=True,
        verbose_name='根本原因'
    )
    corrective_action = models.TextField(
        blank=True,
        verbose_name='纠正措施'
    )
    preventive_action = models.TextField(
        blank=True,
        verbose_name='预防措施'
    )
    related_defect_types = models.ManyToManyField(
        DefectType,
        blank=True,
        related_name='quality_issues',
        verbose_name='关联缺陷类型'
    )
    related_recipes = models.ManyToManyField(
        ProcessRecipe,
        blank=True,
        related_name='quality_issues',
        verbose_name='关联工艺配方'
    )
    raised_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='提出人'
    )
    raised_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='提出时间'
    )
    assigned_to = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='负责人'
    )
    resolved_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='解决人'
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='解决时间'
    )
    closed_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='关闭人'
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='关闭时间'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='备注'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '质量问题'
        verbose_name_plural = '质量问题'
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return f'{self.issue_code} - {self.issue_title}'

    @property
    def status_color_class(self):
        mapping = {
            self.STATUS_OPEN: 'badge-danger',
            self.STATUS_INVESTIGATING: 'badge-warning',
            self.STATUS_RESOLVED: 'badge-info',
            self.STATUS_CLOSED: 'badge-success',
        }
        return mapping.get(self.status, 'badge-gray')

    @property
    def priority_color_class(self):
        mapping = {
            self.PRIORITY_LOW: 'badge-info',
            self.PRIORITY_MEDIUM: 'badge-warning',
            self.PRIORITY_HIGH: 'badge-danger',
            self.PRIORITY_CRITICAL: 'badge-danger',
        }
        return mapping.get(self.priority, 'badge-gray')

    @property
    def affected_batch_count(self):
        return self.affected_batches.count()

    def add_affected_batch(self, batch, notes=''):
        return QualityIssueBatch.objects.create(
            quality_issue=self,
            batch=batch,
            notes=notes
        )


class QualityIssueBatch(models.Model):
    quality_issue = models.ForeignKey(
        QualityIssue,
        on_delete=models.CASCADE,
        related_name='affected_batches',
        verbose_name='质量问题'
    )
    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='quality_issues',
        verbose_name='材料批次'
    )
    impact_level = models.CharField(
        max_length=20,
        choices=[
            ('direct', '直接影响'),
            ('indirect', '间接影响'),
            ('potential', '潜在影响'),
        ],
        default='potential',
        verbose_name='影响程度'
    )
    is_confirmed = models.BooleanField(
        default=False,
        verbose_name='是否确认'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='备注'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='关联时间'
    )

    class Meta:
        verbose_name = '质量问题批次关联'
        verbose_name_plural = '质量问题批次关联'
        ordering = ['-created_at']
        unique_together = [['quality_issue', 'batch']]

    def __str__(self):
        return f'{self.quality_issue.issue_code} - {self.batch.batch_number}'


class ProcessRiskPoint(models.Model):
    RISK_LEVEL_LOW = 'low'
    RISK_LEVEL_MEDIUM = 'medium'
    RISK_LEVEL_HIGH = 'high'
    RISK_LEVEL_CRITICAL = 'critical'

    RISK_LEVEL_CHOICES = [
        (RISK_LEVEL_LOW, '低风险'),
        (RISK_LEVEL_MEDIUM, '中风险'),
        (RISK_LEVEL_HIGH, '高风险'),
        (RISK_LEVEL_CRITICAL, '极高风险'),
    ]

    CATEGORY_MATERIAL = 'material'
    CATEGORY_PROCESS = 'process'
    CATEGORY_EQUIPMENT = 'equipment'
    CATEGORY_ENVIRONMENT = 'environment'
    CATEGORY_OPERATION = 'operation'

    CATEGORY_CHOICES = [
        (CATEGORY_MATERIAL, '原材料'),
        (CATEGORY_PROCESS, '工艺参数'),
        (CATEGORY_EQUIPMENT, '设备状态'),
        (CATEGORY_ENVIRONMENT, '环境条件'),
        (CATEGORY_OPERATION, '操作规范'),
    ]

    recipe = models.ForeignKey(
        ProcessRecipe,
        on_delete=models.CASCADE,
        related_name='risk_points',
        verbose_name='所属配方'
    )
    risk_code = models.CharField(
        max_length=50,
        verbose_name='风险点编号'
    )
    risk_name = models.CharField(
        max_length=200,
        verbose_name='风险点名称'
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_PROCESS,
        verbose_name='风险类别'
    )
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default=RISK_LEVEL_MEDIUM,
        verbose_name='风险等级'
    )
    risk_score = models.FloatField(
        default=50,
        verbose_name='风险评分(0-100)',
        help_text='综合风险评分，越高风险越大'
    )
    process_step = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='工艺环节'
    )
    related_param = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='关联参数'
    )
    description = models.TextField(
        blank=True,
        verbose_name='风险描述'
    )
    potential_consequences = models.TextField(
        blank=True,
        verbose_name='潜在后果'
    )
    likelihood = models.FloatField(
        default=5,
        verbose_name='发生可能性(1-10)',
        help_text='风险发生的可能性，1最低，10最高'
    )
    severity = models.FloatField(
        default=5,
        verbose_name='影响严重度(1-10)',
        help_text='风险发生后的影响严重程度，1最低，10最高'
    )
    detectability = models.FloatField(
        default=5,
        verbose_name='可检测性(1-10)',
        help_text='风险的可检测程度，1最易检测，10最难检测'
    )
    control_measures = models.TextField(
        blank=True,
        verbose_name='控制措施'
    )
    mitigation_plan = models.TextField(
        blank=True,
        verbose_name='缓解方案'
    )
    is_monitored = models.BooleanField(
        default=True,
        verbose_name='是否监控'
    )
    monitoring_method = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='监控方式'
    )
    incident_count = models.IntegerField(
        default=0,
        verbose_name='发生次数'
    )
    related_defect_types = models.ManyToManyField(
        DefectType,
        blank=True,
        related_name='risk_points',
        verbose_name='关联缺陷类型'
    )
    identified_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='识别人'
    )
    identified_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='识别时间'
    )
    last_updated_by = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='最后更新人'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='备注'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新时间'
    )

    class Meta:
        verbose_name = '工艺风险点'
        verbose_name_plural = '工艺风险点'
        ordering = ['-risk_score', 'category']
        unique_together = [['recipe', 'risk_code']]

    def __str__(self):
        return f'{self.recipe.recipe_code} - {self.risk_name}'

    @property
    def risk_color_class(self):
        mapping = {
            self.RISK_LEVEL_LOW: 'badge-success',
            self.RISK_LEVEL_MEDIUM: 'badge-warning',
            self.RISK_LEVEL_HIGH: 'badge-danger',
            self.RISK_LEVEL_CRITICAL: 'badge-danger',
        }
        return mapping.get(self.risk_level, 'badge-gray')

    def save(self, *args, **kwargs):
        self.risk_score = round(
            (self.likelihood * self.severity * self.detectability) / 10, 2
        )
        if self.risk_score < 30:
            self.risk_level = self.RISK_LEVEL_LOW
        elif self.risk_score < 60:
            self.risk_level = self.RISK_LEVEL_MEDIUM
        elif self.risk_score < 85:
            self.risk_level = self.RISK_LEVEL_HIGH
        else:
            self.risk_level = self.RISK_LEVEL_CRITICAL
        super().save(*args, **kwargs)


class QualityTrendRecord(models.Model):
    TREND_TYPE_DAILY = 'daily'
    TREND_TYPE_WEEKLY = 'weekly'
    TREND_TYPE_MONTHLY = 'monthly'

    TREND_TYPE_CHOICES = [
        (TREND_TYPE_DAILY, '每日'),
        (TREND_TYPE_WEEKLY, '每周'),
        (TREND_TYPE_MONTHLY, '每月'),
    ]

    record_date = models.DateField(
        verbose_name='记录日期'
    )
    trend_type = models.CharField(
        max_length=20,
        choices=TREND_TYPE_CHOICES,
        default=TREND_TYPE_DAILY,
        verbose_name='趋势类型'
    )
    total_batches = models.IntegerField(
        default=0,
        verbose_name='总批次数'
    )
    new_batches = models.IntegerField(
        default=0,
        verbose_name='新增批次数'
    )
    defect_count = models.IntegerField(
        default=0,
        verbose_name='缺陷总数'
    )
    defect_rate = models.FloatField(
        default=0,
        verbose_name='缺陷率(%)'
    )
    fracture_count = models.IntegerField(
        default=0,
        verbose_name='断裂次数'
    )
    fracture_rate = models.FloatField(
        default=0,
        verbose_name='断裂率(%)'
    )
    avg_durability_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='平均耐久性评分'
    )
    avg_stability_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='平均稳定性评分'
    )
    avg_rebound_rate = models.FloatField(
        null=True,
        blank=True,
        verbose_name='平均回弹率(%)'
    )
    avg_tensile_strength = models.FloatField(
        null=True,
        blank=True,
        verbose_name='平均抗拉强度(MPa)'
    )
    avg_fatigue_cycles = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='平均疲劳循环次数'
    )
    quality_score = models.FloatField(
        default=80,
        verbose_name='综合质量评分(0-100)',
        help_text='综合质量评分，越高质量越好'
    )
    anomaly_count = models.IntegerField(
        default=0,
        verbose_name='异常数据数'
    )
    resolved_quality_issues = models.IntegerField(
        default=0,
        verbose_name='已解决质量问题数'
    )
    open_quality_issues = models.IntegerField(
        default=0,
        verbose_name='待解决质量问题数'
    )
    category_distribution = models.JSONField(
        default=dict,
        verbose_name='缺陷类别分布'
    )
    top_defect_types = models.JSONField(
        default=list,
        verbose_name='主要缺陷类型'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='备注'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '质量趋势记录'
        verbose_name_plural = '质量趋势记录'
        ordering = ['-record_date']
        unique_together = [['record_date', 'trend_type']]

    def __str__(self):
        return f'{self.record_date} - {self.get_trend_type_display()}'


class TraceabilityLink(models.Model):
    LINK_TYPE_MATERIAL = 'material'
    LINK_TYPE_PROCESS = 'process'
    LINK_TYPE_TEST = 'test'
    LINK_TYPE_DEFECT = 'defect'
    LINK_TYPE_DIAGNOSIS = 'diagnosis'

    LINK_TYPE_CHOICES = [
        (LINK_TYPE_MATERIAL, '材料批次'),
        (LINK_TYPE_PROCESS, '工艺配方'),
        (LINK_TYPE_TEST, '测试记录'),
        (LINK_TYPE_DEFECT, '缺陷记录'),
        (LINK_TYPE_DIAGNOSIS, '断裂诊断'),
    ]

    batch = models.ForeignKey(
        MaterialBatch,
        on_delete=models.CASCADE,
        related_name='traceability_links',
        verbose_name='材料批次'
    )
    link_type = models.CharField(
        max_length=30,
        choices=LINK_TYPE_CHOICES,
        verbose_name='链路类型'
    )
    link_id = models.IntegerField(
        verbose_name='关联记录ID'
    )
    link_title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='链路标题'
    )
    link_description = models.TextField(
        blank=True,
        verbose_name='链路描述'
    )
    sequence = models.IntegerField(
        default=0,
        verbose_name='顺序'
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='创建时间'
    )

    class Meta:
        verbose_name = '追溯链路'
        verbose_name_plural = '追溯链路'
        ordering = ['batch', 'sequence', '-created_at']

    def __str__(self):
        return f'{self.batch.batch_number} - {self.get_link_type_display()}'
