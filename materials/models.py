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
