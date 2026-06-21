from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class MaterialBatch(models.Model):
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
        if self.diameter <= 0:
            raise ValidationError({'diameter': '直径必须大于0'})
        if self.initial_length <= 0:
            raise ValidationError({'initial_length': '初始长度必须大于0'})
        super().clean()

    @property
    def is_broken(self):
        return self.tension_tests.filter(is_broken=True).exists()

    @property
    def latest_test(self):
        return self.tension_tests.order_by('-test_time').first()

    @property
    def test_count(self):
        return self.tension_tests.count()


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
        return f'{self.batch.batch_number} - {self.tension_force}N - {status}'

    def clean(self):
        if self.tension_force <= 0:
            raise ValidationError({'tension_force': '拉力值必须大于0'})
        if self.elongation < 0:
            raise ValidationError({'elongation': '伸长量不能为负数'})
        if self.length_before_rebound is not None:
            if self.length_before_rebound <= 0:
                raise ValidationError({'length_before_rebound': '回弹前长度必须大于0'})
        if self.length_after_rebound is not None:
            if self.length_after_rebound <= 0:
                raise ValidationError({'length_after_rebound': '回弹后长度必须大于0'})
        if self.abnormal_break and not self.break_reason.strip():
            raise ValidationError({'break_reason': '异常断裂必须填写原因'})
        if self.is_broken:
            previous_tests = TensionTest.objects.filter(
                batch=self.batch,
                is_broken=True
            )
            if self.pk:
                previous_tests = previous_tests.exclude(pk=self.pk)
            if previous_tests.exists():
                raise ValidationError('该批次样本已断裂，不能继续新增测试记录')
        else:
            previous_broken = TensionTest.objects.filter(
                batch=self.batch,
                is_broken=True
            )
            if self.pk:
                previous_broken = previous_broken.exclude(pk=self.pk)
            if previous_broken.exists():
                raise ValidationError('该批次样本已断裂，不能继续新增测试记录')
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        if (self.length_before_rebound is not None
                and self.length_after_rebound is not None
                and self.elongation > 0):
            initial = self.batch.initial_length
            elastic_deformation = self.length_before_rebound - initial
            if elastic_deformation > 0:
                rebound = self.length_before_rebound - self.length_after_rebound
                self.rebound_rate = round((rebound / elastic_deformation) * 100, 2)
            else:
                self.rebound_rate = None
        else:
            self.rebound_rate = None
        super().save(*args, **kwargs)
