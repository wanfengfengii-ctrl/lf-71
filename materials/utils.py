import math
from datetime import date
from .models import (
    MaterialBatch, TensionTest, FatigueTest, DataAnomalyLog,
    StatisticalSnapshot, BreakageFlowRecord,
)


class AnomalyDetector:
    FORCE_DEVIATION_THRESHOLD = 0.5
    ELONGATION_DEVIATION_THRESHOLD = 0.5
    REBOUND_RATE_MIN = 0
    REBOUND_RATE_MAX = 100
    STRESS_STRAIN_RATIO_THRESHOLD = 3.0
    FATIGUE_CYCLE_DEVIATION_THRESHOLD = 0.6
    FATIGUE_LOAD_DEVIATION_THRESHOLD = 0.5

    def __init__(self, batch):
        self.batch = batch

    def check_tension_test(self, test, exclude_pk=None):
        anomalies = []
        existing = TensionTest.objects.filter(
            batch=self.batch, is_flagged=False
        )
        if exclude_pk:
            existing = existing.exclude(pk=exclude_pk)

        if not existing.exists():
            return anomalies

        forces = list(existing.values_list('tension_force', flat=True))
        elongations = list(existing.values_list('elongation', flat=True))
        rebound_rates = list(
            existing.filter(rebound_rate__isnull=False).values_list('rebound_rate', flat=True)
        )

        if forces:
            avg_force = sum(forces) / len(forces)
            if avg_force > 0:
                deviation = abs(test.tension_force - avg_force) / avg_force
                if deviation > self.FORCE_DEVIATION_THRESHOLD:
                    anomalies.append({
                        'field': 'tension_force',
                        'severity': DataAnomalyLog.SEVERITY_HIGH,
                        'description': (
                            f'拉力值{test.tension_force}N与批次均值{avg_force:.1f}N'
                            f'偏差超过{self.FORCE_DEVIATION_THRESHOLD * 100:.0f}%'
                        ),
                    })

            force_std = self._std_dev(forces)
            if force_std > 0 and avg_force > 0:
                z_score = abs(test.tension_force - avg_force) / force_std
                if z_score > 2.0:
                    anomalies.append({
                        'field': 'tension_force',
                        'severity': DataAnomalyLog.SEVERITY_MEDIUM,
                        'description': (
                            f'拉力值{test.tension_force}N的Z得分为{z_score:.2f}，'
                            f'超过2倍标准差'
                        ),
                    })

        if elongations:
            avg_elong = sum(elongations) / len(elongations)
            if avg_elong > 0:
                deviation = abs(test.elongation - avg_elong) / avg_elong
                if deviation > self.ELONGATION_DEVIATION_THRESHOLD:
                    anomalies.append({
                        'field': 'elongation',
                        'severity': DataAnomalyLog.SEVERITY_MEDIUM,
                        'description': (
                            f'伸长量{test.elongation}mm与批次均值{avg_elong:.1f}mm'
                            f'偏差超过{self.ELONGATION_DEVIATION_THRESHOLD * 100:.0f}%'
                        ),
                    })

        if test.rebound_rate is not None:
            if test.rebound_rate < self.REBOUND_RATE_MIN or test.rebound_rate > self.REBOUND_RATE_MAX:
                anomalies.append({
                    'field': 'rebound_rate',
                    'severity': DataAnomalyLog.SEVERITY_HIGH,
                    'description': (
                        f'回弹率{test.rebound_rate}%超出合理范围'
                        f'({self.REBOUND_RATE_MIN}%-{self.REBOUND_RATE_MAX}%)'
                    ),
                })
            if rebound_rates:
                avg_rebound = sum(rebound_rates) / len(rebound_rates)
                if avg_rebound > 0:
                    deviation = abs(test.rebound_rate - avg_rebound) / avg_rebound
                    if deviation > 0.4:
                        anomalies.append({
                            'field': 'rebound_rate',
                            'severity': DataAnomalyLog.SEVERITY_MEDIUM,
                            'description': (
                                f'回弹率{test.rebound_rate}%与批次均值{avg_rebound:.1f}%'
                                f'偏差超过40%'
                            ),
                        })

        if test.tension_force > 0 and test.elongation > 0:
            ratio = test.tension_force / test.elongation
            ratios = [f / e for f, e in zip(forces, elongations) if e > 0]
            if ratios:
                avg_ratio = sum(ratios) / len(ratios)
                if avg_ratio > 0:
                    deviation = abs(ratio - avg_ratio) / avg_ratio
                    if deviation > self.STRESS_STRAIN_RATIO_THRESHOLD:
                        anomalies.append({
                            'field': 'tension_force',
                            'severity': DataAnomalyLog.SEVERITY_HIGH,
                            'description': (
                                f'拉力-伸长比值{ratio:.2f}与批次均值{avg_ratio:.2f}'
                                f'偏差异常'
                            ),
                        })

        return anomalies

    def check_fatigue_test(self, test, exclude_pk=None):
        anomalies = []
        existing = FatigueTest.objects.filter(
            batch=self.batch, is_flagged=False
        )
        if exclude_pk:
            existing = existing.exclude(pk=exclude_pk)

        if not existing.exists():
            return anomalies

        cycles = list(existing.values_list('cycle_count', flat=True))
        loads = list(existing.values_list('load_force', flat=True))

        if cycles:
            avg_cycles = sum(cycles) / len(cycles)
            if avg_cycles > 0:
                deviation = abs(test.cycle_count - avg_cycles) / avg_cycles
                if deviation > self.FATIGUE_CYCLE_DEVIATION_THRESHOLD:
                    anomalies.append({
                        'field': 'cycle_count',
                        'severity': DataAnomalyLog.SEVERITY_MEDIUM,
                        'description': (
                            f'循环次数{test.cycle_count}与批次均值{avg_cycles:.0f}'
                            f'偏差超过{self.FATIGUE_CYCLE_DEVIATION_THRESHOLD * 100:.0f}%'
                        ),
                    })

        if loads:
            avg_load = sum(loads) / len(loads)
            if avg_load > 0:
                deviation = abs(test.load_force - avg_load) / avg_load
                if deviation > self.FATIGUE_LOAD_DEVIATION_THRESHOLD:
                    anomalies.append({
                        'field': 'load_force',
                        'severity': DataAnomalyLog.SEVERITY_HIGH,
                        'description': (
                            f'加载力{test.load_force}N与批次均值{avg_load:.1f}N'
                            f'偏差超过{self.FATIGUE_LOAD_DEVIATION_THRESHOLD * 100:.0f}%'
                        ),
                    })

        if test.result == FatigueTest.RESULT_INTACT and test.cycle_count > 0:
            avg_cycles_to_failure = None
            broken = existing.filter(result=FatigueTest.RESULT_BROKEN)
            if broken.exists():
                broken_cycles = list(broken.values_list('cycle_count', flat=True))
                avg_cycles_to_failure = sum(broken_cycles) / len(broken_cycles)
            if avg_cycles_to_failure and test.cycle_count > avg_cycles_to_failure * 1.5:
                anomalies.append({
                    'field': 'cycle_count',
                    'severity': DataAnomalyLog.SEVERITY_LOW,
                    'description': (
                        f'完好循环次数{test.cycle_count}远超批次平均断裂循环次数'
                        f'{avg_cycles_to_failure:.0f}'
                    ),
                })

        return anomalies

    def create_anomaly_logs(self, anomalies, source_type, source_id):
        for anomaly in anomalies:
            DataAnomalyLog.objects.create(
                batch=self.batch,
                source_type=source_type,
                source_id=source_id,
                anomaly_description=anomaly['description'],
                severity=anomaly['severity'],
            )

    @staticmethod
    def _std_dev(values):
        if not values or len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)


class StatisticsAnalyzer:
    def __init__(self):
        pass

    @staticmethod
    def basic_stats(values):
        if not values:
            return None
        n = len(values)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n if n > 0 else 0
        std = math.sqrt(variance)
        sorted_vals = sorted(values)
        median = sorted_vals[n // 2] if n % 2 == 1 else (
            sorted_vals[n // 2 - 1] + sorted_vals[n // 2]
        ) / 2
        return {
            'count': n,
            'min': round(min(values), 4),
            'max': round(max(values), 4),
            'mean': round(mean, 4),
            'median': round(median, 4),
            'std': round(std, 4),
            'variance': round(variance, 4),
            'range': round(max(values) - min(values), 4),
        }

    @staticmethod
    def percentile(values, p):
        if not values:
            return None
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

    @staticmethod
    def correlation(x_values, y_values):
        if not x_values or not y_values or len(x_values) != len(y_values):
            return None
        n = len(x_values)
        if n < 2:
            return None
        mean_x = sum(x_values) / n
        mean_y = sum(y_values) / n
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
        denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in x_values))
        denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in y_values))
        if denom_x == 0 or denom_y == 0:
            return 0
        return round(numerator / (denom_x * denom_y), 4)

    @staticmethod
    def linear_regression(x_values, y_values):
        if not x_values or not y_values or len(x_values) != len(y_values):
            return None
        n = len(x_values)
        if n < 2:
            return None
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_xx = sum(x ** 2 for x in x_values)
        denom = n * sum_xx - sum_x ** 2
        if denom == 0:
            return None
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        mean_y = sum_y / n
        ss_tot = sum((y - mean_y) ** 2 for y in y_values)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        return {
            'slope': round(slope, 6),
            'intercept': round(intercept, 6),
            'r_squared': round(r_squared, 4),
        }

    def get_batch_comprehensive_stats(self, batch):
        tension_tests = batch.tension_tests.filter(is_flagged=False)
        fatigue_tests = batch.fatigue_tests.filter(is_flagged=False)
        result = {
            'batch_info': {
                'batch_number': batch.batch_number,
                'material_source': batch.material_source,
                'diameter': batch.diameter,
                'initial_length': batch.initial_length,
                'status': batch.get_status_display(),
            },
            'tension': None,
            'fatigue': None,
            'derived': {},
        }

        if tension_tests.exists():
            forces = list(tension_tests.values_list('tension_force', flat=True))
            elongations = list(tension_tests.values_list('elongation', flat=True))
            rebounds = list(
                tension_tests.filter(rebound_rate__isnull=False).values_list('rebound_rate', flat=True)
            )
            stresses = []
            strains = []
            for t in tension_tests:
                if t.stress is not None:
                    stresses.append(t.stress)
                if t.strain is not None:
                    strains.append(t.strain)

            result['tension'] = {
                'test_count': tension_tests.count(),
                'force': self.basic_stats(forces),
                'elongation': self.basic_stats(elongations),
                'rebound_rate': self.basic_stats(rebounds) if rebounds else None,
                'stress': self.basic_stats(stresses) if stresses else None,
                'strain': self.basic_stats(strains) if strains else None,
                'force_elongation_correlation': self.correlation(elongations, forces),
                'stress_strain_regression': (
                    self.linear_regression(strains, stresses)
                    if len(strains) >= 2 and len(stresses) >= 2 else None
                ),
            }

            broken = tension_tests.filter(is_broken=True)
            if broken.exists():
                breaking_forces = list(broken.values_list('tension_force', flat=True))
                breaking_elongations = list(broken.values_list('elongation', flat=True))
                result['derived'].update({
                    'breaking_force': self.basic_stats(breaking_forces),
                    'breaking_elongation': self.basic_stats(breaking_elongations),
                    'tensile_strength': batch.tensile_strength,
                    'elongation_at_break': batch.elongation_at_break,
                })
            result['derived']['youngs_modulus'] = batch.youngs_modulus

        if fatigue_tests.exists():
            cycles = list(fatigue_tests.values_list('cycle_count', flat=True))
            loads = list(fatigue_tests.values_list('load_force', flat=True))
            result['fatigue'] = {
                'test_count': fatigue_tests.count(),
                'cycles': self.basic_stats(cycles),
                'load': self.basic_stats(loads),
                'cycles_to_failure': batch.fatigue_cycles_to_failure,
                'endurance_limit': batch.fatigue_endurance_limit,
                'load_cycle_correlation': self.correlation(cycles, loads),
            }

        return result

    def get_global_statistics(self):
        batches = MaterialBatch.objects.all()
        tension_tests = TensionTest.objects.filter(is_flagged=False)
        fatigue_tests = FatigueTest.objects.filter(is_flagged=False)

        forces = list(tension_tests.values_list('tension_force', flat=True))
        elongations = list(tension_tests.values_list('elongation', flat=True))
        rebounds = list(
            tension_tests.filter(rebound_rate__isnull=False).values_list('rebound_rate', flat=True)
        )
        cycles = list(fatigue_tests.values_list('cycle_count', flat=True))
        loads = list(fatigue_tests.values_list('load_force', flat=True))

        status_dist = {}
        for val, label in MaterialBatch.STATUS_CHOICES:
            status_dist[val] = {
                'label': label,
                'count': batches.filter(status=val).count(),
            }

        source_dist = {}
        for batch in batches:
            src = batch.material_source
            if src not in source_dist:
                source_dist[src] = 0
            source_dist[src] += 1

        return {
            'summary': {
                'total_batches': batches.count(),
                'active_batches': batches.filter(
                    status__in=[MaterialBatch.STATUS_ACTIVE, MaterialBatch.STATUS_TESTING]
                ).count(),
                'broken_batches': sum(1 for b in batches if b.is_broken),
                'archived_batches': batches.filter(status=MaterialBatch.STATUS_ARCHIVED).count(),
                'total_tension_tests': tension_tests.count(),
                'total_fatigue_tests': fatigue_tests.count(),
                'total_anomalies': DataAnomalyLog.objects.count(),
                'unresolved_anomalies': DataAnomalyLog.objects.filter(is_resolved=False).count(),
            },
            'tension': {
                'force': self.basic_stats(forces),
                'elongation': self.basic_stats(elongations),
                'rebound_rate': self.basic_stats(rebounds) if rebounds else None,
            },
            'fatigue': {
                'cycles': self.basic_stats(cycles),
                'load': self.basic_stats(loads),
            },
            'status_distribution': status_dist,
            'source_distribution': [
                {'source': k, 'count': v} for k, v in sorted(source_dist.items(), key=lambda x: -x[1])
            ],
            'trend': self._build_trend_data(),
        }

    def _build_trend_data(self):
        from django.db.models import Count
        from datetime import timedelta
        today = date.today()
        trend = []
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            tension_count = TensionTest.objects.filter(test_time__date=d).count()
            fatigue_count = FatigueTest.objects.filter(test_time__date=d).count()
            batch_count = MaterialBatch.objects.filter(created_at__date=d).count()
            anomaly_count = DataAnomalyLog.objects.filter(created_at__date=d).count()
            trend.append({
                'date': d.isoformat(),
                'tension_tests': tension_count,
                'fatigue_tests': fatigue_count,
                'new_batches': batch_count,
                'anomalies': anomaly_count,
            })
        return trend


class ReboundRateCalculator:
    @staticmethod
    def calculate(initial_length, length_before_rebound, length_after_rebound):
        if initial_length is None or length_before_rebound is None or length_after_rebound is None:
            return None
        if initial_length <= 0 or length_before_rebound <= 0 or length_after_rebound <= 0:
            return None
        elastic_deformation = length_before_rebound - initial_length
        if elastic_deformation <= 0:
            return None
        rebound = length_before_rebound - length_after_rebound
        if rebound < 0:
            return None
        return round((rebound / elastic_deformation) * 100, 2)

    @staticmethod
    def validate_inputs(initial_length, length_before_rebound, length_after_rebound):
        errors = []
        if initial_length is not None and initial_length <= 0:
            errors.append('初始长度必须大于0')
        if length_before_rebound is not None:
            if length_before_rebound <= 0:
                errors.append('回弹前长度必须大于0')
            elif initial_length is not None and length_before_rebound < initial_length:
                errors.append('回弹前长度不能小于初始长度')
        if length_after_rebound is not None:
            if length_after_rebound <= 0:
                errors.append('回弹后长度必须大于0')
            elif length_before_rebound is not None and length_after_rebound > length_before_rebound:
                errors.append('回弹后长度不能大于回弹前长度')
            elif initial_length is not None and length_after_rebound < initial_length:
                errors.append('回弹后长度不能小于初始长度')
        return errors


class SnapshotGenerator:
    @staticmethod
    def generate_daily():
        today = date.today()
        batches = MaterialBatch.objects.all()
        tension_tests = TensionTest.objects.all()
        fatigue_tests = FatigueTest.objects.all()
        anomalies = DataAnomalyLog.objects.all()

        avg_force = None
        avg_elongation = None
        avg_rebound = None
        rebound_tests = tension_tests.filter(rebound_rate__isnull=False)
        if tension_tests.exists():
            forces = list(tension_tests.values_list('tension_force', flat=True))
            elongations = list(tension_tests.values_list('elongation', flat=True))
            avg_force = round(sum(forces) / len(forces), 2)
            avg_elongation = round(sum(elongations) / len(elongations), 2)
        if rebound_tests.exists():
            rebounds = list(rebound_tests.values_list('rebound_rate', flat=True))
            avg_rebound = round(sum(rebounds) / len(rebounds), 2)

        snapshot, created = StatisticalSnapshot.objects.update_or_create(
            snapshot_date=today,
            snapshot_type=StatisticalSnapshot.SNAPSHOT_TYPE_DAILY,
            defaults={
                'total_batches': batches.count(),
                'active_batches': batches.filter(
                    status__in=[MaterialBatch.STATUS_ACTIVE, MaterialBatch.STATUS_TESTING]
                ).count(),
                'broken_batches': sum(1 for b in batches if b.is_broken),
                'total_tension_tests': tension_tests.count(),
                'total_fatigue_tests': fatigue_tests.count(),
                'avg_force': avg_force,
                'avg_elongation': avg_elongation,
                'avg_rebound_rate': avg_rebound,
                'anomaly_count': anomalies.count(),
                'resolved_anomaly_count': anomalies.filter(is_resolved=True).count(),
            },
        )
        return snapshot, created


class BreakFlowManager:
    @staticmethod
    def start_review(batch, operator='', notes=''):
        if batch.status not in (MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW):
            return False, '该批次不在断裂状态'
        batch.status = MaterialBatch.STATUS_REVIEW
        batch.save(update_fields=['status'])
        batch.record_flow_action(
            action=BreakageFlowRecord.ACTION_REVIEW_START,
            notes=notes,
            operator=operator,
        )
        return True, '已进入审核状态'

    @staticmethod
    def archive_batch(batch, operator='', review_notes=''):
        if batch.status not in (MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW):
            return False, '该批次不在可归档状态'
        from django.utils import timezone
        batch.status = MaterialBatch.STATUS_ARCHIVED
        batch.reviewed_at = timezone.now()
        batch.review_notes = review_notes
        batch.save()
        batch.record_flow_action(
            action=BreakageFlowRecord.ACTION_ARCHIVED,
            notes=review_notes,
            operator=operator,
        )
        return True, '批次已归档'

    @staticmethod
    def reactivate_batch(batch, operator='', review_notes=''):
        if batch.status not in (MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW):
            return False, '该批次不在可恢复状态'
        from django.utils import timezone
        batch.status = MaterialBatch.STATUS_ACTIVE
        batch.reviewed_at = timezone.now()
        batch.review_notes = review_notes
        batch.broken_at = None
        batch.save()
        batch.tension_tests.filter(is_broken=True).update(
            is_broken=False, abnormal_break=False, break_reason=''
        )
        batch.fatigue_tests.filter(result=FatigueTest.RESULT_BROKEN).update(
            result=FatigueTest.RESULT_INTACT
        )
        batch.record_flow_action(
            action=BreakageFlowRecord.ACTION_REACTIVATED,
            notes=review_notes,
            operator=operator,
        )
        return True, '批次已恢复为正常状态'
