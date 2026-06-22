import math
from datetime import date
from collections import defaultdict
from .models import (
    MaterialBatch, TensionTest, FatigueTest, DataAnomalyLog,
    StatisticalSnapshot, BreakageFlowRecord,
    BowType, LifePrediction, MaterialRecommendation,
    BowTypeMatching, BatchRanking,
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


class LifePredictor:
    WEIGHT_DURABILITY = 0.45
    WEIGHT_STABILITY = 0.35
    WEIGHT_ANOMALY = 0.20

    BENCHMARK_TENSILE_STRENGTH = 800
    BENCHMARK_FATIGUE_CYCLES = 10000
    BENCHMARK_REBOUND_RATE = 90
    BENCHMARK_ELONGATION_AT_BREAK = 15

    def __init__(self, batch):
        self.batch = batch
        self.analyzer = StatisticsAnalyzer()

    def calculate_durability_score(self):
        score = 50.0
        factors = []
        details = {}

        tensile_strength = self.batch.tensile_strength
        if tensile_strength is not None:
            ratio = min(tensile_strength / self.BENCHMARK_TENSILE_STRENGTH, 1.5)
            ts_score = min(ratio * 40, 60)
            score += ts_score
            factors.append(f'抗拉强度达标率{ratio * 100:.0f}%')
            details['tensile_strength_score'] = round(ts_score, 1)
            details['tensile_strength_value'] = tensile_strength

        cycles = self.batch.fatigue_cycles_to_failure
        if cycles is not None:
            ratio = min(cycles / self.BENCHMARK_FATIGUE_CYCLES, 2.0)
            fatigue_score = min(ratio * 30, 45)
            score += fatigue_score
            factors.append(f'断裂循环次数达标率{ratio * 100:.0f}%')
            details['fatigue_cycles_score'] = round(fatigue_score, 1)
            details['fatigue_cycles_value'] = cycles

        endurance = self.batch.fatigue_endurance_limit
        if endurance is not None:
            end_score = min(endurance / 500 * 15, 20)
            score += end_score
            factors.append(f'疲劳极限载荷{endurance:.0f}N')
            details['endurance_limit_score'] = round(end_score, 1)
            details['endurance_limit_value'] = endurance

        youngs = self.batch.youngs_modulus
        if youngs is not None:
            if 1000 <= youngs <= 20000:
                ym_score = 15
            elif 500 <= youngs < 1000 or 20000 < youngs <= 50000:
                ym_score = 8
            else:
                ym_score = 3
            score += ym_score
            factors.append(f'杨氏模量{youngs:.0f}MPa')
            details['youngs_modulus_score'] = ym_score
            details['youngs_modulus_value'] = youngs

        score = min(score, 100)
        return round(score, 1), factors, details

    def calculate_stability_score(self):
        score = 50.0
        factors = []
        details = {}

        avg_rebound = self.batch.avg_rebound_rate
        if avg_rebound is not None:
            if avg_rebound >= self.BENCHMARK_REBOUND_RATE:
                rr_score = 40
            elif avg_rebound >= 80:
                rr_score = 30
            elif avg_rebound >= 70:
                rr_score = 20
            elif avg_rebound >= 60:
                rr_score = 10
            else:
                rr_score = 5
            score += rr_score - 10
            factors.append(f'平均回弹率{avg_rebound:.1f}%')
            details['rebound_score'] = rr_score
            details['rebound_value'] = avg_rebound

        rebound_tests = self.batch.tension_tests.filter(
            rebound_rate__isnull=False, is_flagged=False
        )
        if rebound_tests.count() >= 3:
            rebounds = list(rebound_tests.values_list('rebound_rate', flat=True))
            mean_r = sum(rebounds) / len(rebounds)
            if mean_r > 0:
                variance = sum((r - mean_r) ** 2 for r in rebounds) / len(rebounds)
                cv = math.sqrt(variance) / mean_r
                if cv < 0.05:
                    cons_score = 30
                elif cv < 0.10:
                    cons_score = 22
                elif cv < 0.15:
                    cons_score = 15
                elif cv < 0.20:
                    cons_score = 8
                else:
                    cons_score = 3
                score += cons_score
                factors.append(f'回弹率变异系数{cv * 100:.1f}%')
                details['consistency_score'] = cons_score
                details['cv_value'] = round(cv * 100, 2)

        elong_break = self.batch.elongation_at_break
        if elong_break is not None:
            ratio = min(elong_break / self.BENCHMARK_ELONGATION_AT_BREAK, 1.5)
            eb_score = min(ratio * 20, 30)
            score += eb_score
            factors.append(f'断裂伸长率{elong_break:.1f}%')
            details['elongation_break_score'] = round(eb_score, 1)
            details['elongation_break_value'] = elong_break

        tension_tests = self.batch.tension_tests.filter(is_flagged=False)
        if tension_tests.count() >= 5:
            forces = list(tension_tests.values_list('tension_force', flat=True))
            mean_f = sum(forces) / len(forces)
            if mean_f > 0:
                var_f = sum((f - mean_f) ** 2 for f in forces) / len(forces)
                cv_f = math.sqrt(var_f) / mean_f
                if cv_f < 0.10:
                    fc_score = 15
                elif cv_f < 0.20:
                    fc_score = 10
                elif cv_f < 0.30:
                    fc_score = 5
                else:
                    fc_score = 2
                score += fc_score
                factors.append(f'拉力值变异系数{cv_f * 100:.1f}%')
                details['force_consistency_score'] = fc_score
                details['force_cv'] = round(cv_f * 100, 2)

        score = min(max(score, 0), 100)
        return round(score, 1), factors, details

    def calculate_anomaly_penalty(self):
        penalty = 0.0
        warning_signs = []
        details = {}

        unresolved = self.batch.anomaly_logs.filter(is_resolved=False)
        high_anomalies = unresolved.filter(severity=DataAnomalyLog.SEVERITY_HIGH).count()
        med_anomalies = unresolved.filter(severity=DataAnomalyLog.SEVERITY_MEDIUM).count()
        low_anomalies = unresolved.filter(severity=DataAnomalyLog.SEVERITY_LOW).count()

        penalty += high_anomalies * 15
        penalty += med_anomalies * 8
        penalty += low_anomalies * 3

        if high_anomalies > 0:
            warning_signs.append(f'存在{high_anomalies}项高严重度未处理异常')
        if med_anomalies > 0:
            warning_signs.append(f'存在{med_anomalies}项中严重度未处理异常')

        flagged_tension = self.batch.tension_tests.filter(is_flagged=True).count()
        flagged_fatigue = self.batch.fatigue_tests.filter(is_flagged=True).count()
        total_tests = self.batch.test_count + self.batch.fatigue_test_count
        if total_tests > 0:
            flag_ratio = (flagged_tension + flagged_fatigue) / total_tests
            penalty += flag_ratio * 25
            if flag_ratio > 0.15:
                warning_signs.append(f'异常标记数据占比{flag_ratio * 100:.0f}%，超过15%阈值')

        abnormal_tension = self.batch.tension_tests.filter(abnormal_break=True).count()
        abnormal_fatigue = self.batch.fatigue_tests.filter(abnormal_break=True).count()
        if abnormal_tension > 0 or abnormal_fatigue > 0:
            penalty += (abnormal_tension + abnormal_fatigue) * 12
            warning_signs.append(f'存在异常断裂记录（拉伸:{abnormal_tension}次，疲劳:{abnormal_fatigue}次）')

        details.update({
            'high_anomalies': high_anomalies,
            'medium_anomalies': med_anomalies,
            'low_anomalies': low_anomalies,
            'flagged_tension': flagged_tension,
            'flagged_fatigue': flagged_fatigue,
            'abnormal_breaks': abnormal_tension + abnormal_fatigue,
        })

        return round(penalty, 1), warning_signs, details

    def predict(self):
        durability_score, d_factors, d_details = self.calculate_durability_score()
        stability_score, s_factors, s_details = self.calculate_stability_score()
        anomaly_penalty, w_signs, a_details = self.calculate_anomaly_penalty()

        raw_score = (
            durability_score * self.WEIGHT_DURABILITY
            + stability_score * self.WEIGHT_STABILITY
        )
        life_score = max(0, min(100, raw_score - anomaly_penalty * self.WEIGHT_ANOMALY))
        life_score = round(life_score, 1)

        risk_score = self._calculate_risk_score(
            life_score, durability_score, stability_score, anomaly_penalty
        )

        if risk_score >= 75:
            risk_level = LifePrediction.RISK_LEVEL_CRITICAL
        elif risk_score >= 50:
            risk_level = LifePrediction.RISK_LEVEL_HIGH
        elif risk_score >= 25:
            risk_level = LifePrediction.RISK_LEVEL_MEDIUM
        else:
            risk_level = LifePrediction.RISK_LEVEL_LOW

        pred_cycles = self._predict_cycles_to_failure(durability_score, stability_score)
        pred_hours = self._predict_lifetime_hours(pred_cycles, risk_score)

        key_factors = d_factors + s_factors
        recommendations = self._generate_recommendations(
            durability_score, stability_score, anomaly_penalty, w_signs
        )

        prediction = LifePrediction(
            batch=self.batch,
            life_score=life_score,
            durability_score=durability_score,
            stability_score=stability_score,
            risk_level=risk_level,
            risk_score=risk_score,
            predicted_cycles_to_failure=pred_cycles,
            predicted_lifetime_hours=pred_hours,
            key_factors=key_factors,
            warning_signs=w_signs,
            recommendations=recommendations,
        )
        prediction.save()

        return {
            'prediction': prediction,
            'durability_details': d_details,
            'stability_details': s_details,
            'anomaly_details': a_details,
        }

    def _calculate_risk_score(self, life_score, durability, stability, penalty):
        score = 0.0
        if life_score < 30:
            score += 40
        elif life_score < 50:
            score += 25
        elif life_score < 70:
            score += 10

        if durability < 40:
            score += 20
        elif durability < 60:
            score += 10

        if stability < 40:
            score += 18
        elif stability < 60:
            score += 8

        score += min(penalty, 35)

        if self.batch.status in (MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW):
            score += 30

        return round(min(score, 100), 1)

    def _predict_cycles_to_failure(self, durability, stability):
        base_cycles = self.batch.fatigue_cycles_to_failure
        if base_cycles:
            factor = (durability / 100 * 0.6 + stability / 100 * 0.4)
            cycles = base_cycles * max(0.3, factor)
            return int(cycles)

        score_factor = (durability * 0.6 + stability * 0.4) / 100
        cycles = self.BENCHMARK_FATIGUE_CYCLES * score_factor
        return int(max(cycles, 500))

    def _predict_lifetime_hours(self, cycles, risk_score):
        if cycles is None:
            return None
        typical_cycles_per_hour = 180
        risk_factor = 1.0 - (risk_score / 200)
        hours = (cycles / typical_cycles_per_hour) * risk_factor
        return round(hours, 1)

    def _generate_recommendations(self, durability, stability, penalty, warnings):
        recs = []
        if durability < 50:
            recs.append('耐久性不足，建议提高材料抗拉强度处理工艺，或更换更高强度材料来源')
        if stability < 50:
            recs.append('稳定性较差，建议优化热处理或捻制工艺参数，改善回弹一致性')
        if penalty >= 20:
            recs.append('异常数据较多，建议先排查并处理当前批次的质量问题')
        if warnings:
            recs.append('注意以下预警信号：' + '；'.join(warnings[:3]))
        if not recs:
            recs.append('当前批次综合表现良好，可继续按标准工艺使用')
        return '\n'.join(recs)


class MaterialRecommender:
    WEIGHT_SIMILARITY = 0.4
    WEIGHT_PERFORMANCE = 0.6

    def __init__(self, source_batch):
        self.source_batch = source_batch
        self.predictor = LifePredictor(source_batch)
        self.source_pred = self._get_or_create_prediction(source_batch)

    def _get_or_create_prediction(self, batch):
        pred = LifePrediction.objects.filter(batch=batch, is_latest=True).first()
        if pred is None:
            predictor = LifePredictor(batch)
            result = predictor.predict()
            pred = result['prediction']
        return pred

    def _get_batch_fingerprint(self, batch):
        fp = {
            'diameter': batch.diameter,
            'initial_length': batch.initial_length,
            'material_source': batch.material_source,
            'tensile_strength': batch.tensile_strength or 0,
            'youngs_modulus': batch.youngs_modulus or 0,
            'avg_rebound': batch.avg_rebound_rate or 0,
            'elongation_at_break': batch.elongation_at_break or 0,
            'fatigue_cycles': batch.fatigue_cycles_to_failure or 0,
        }
        pred = LifePrediction.objects.filter(batch=batch, is_latest=True).first()
        if pred:
            fp['life_score'] = pred.life_score
            fp['durability'] = pred.durability_score
            fp['stability'] = pred.stability_score
        else:
            fp['life_score'] = 0
            fp['durability'] = 0
            fp['stability'] = 0
        return fp

    def calculate_similarity(self, batch_a, batch_b):
        fp_a = self._get_batch_fingerprint(batch_a)
        fp_b = self._get_batch_fingerprint(batch_b)
        factors = {}
        total_weight = 0
        weighted_sum = 0

        diam_sim = 1.0 - min(abs(fp_a['diameter'] - fp_b['diameter']) / max(fp_a['diameter'], 0.01), 1.0)
        factors['diameter'] = round(diam_sim * 100, 1)
        weighted_sum += diam_sim * 20
        total_weight += 20

        if fp_a['tensile_strength'] > 0 and fp_b['tensile_strength'] > 0:
            ts_diff = abs(fp_a['tensile_strength'] - fp_b['tensile_strength'])
            ts_sim = 1.0 - min(ts_diff / max(fp_a['tensile_strength'], 1), 1.0)
        else:
            ts_sim = 0.5
        factors['tensile_strength'] = round(ts_sim * 100, 1)
        weighted_sum += ts_sim * 25
        total_weight += 25

        if fp_a['youngs_modulus'] > 0 and fp_b['youngs_modulus'] > 0:
            ym_diff = abs(fp_a['youngs_modulus'] - fp_b['youngs_modulus'])
            ym_sim = 1.0 - min(ym_diff / max(fp_a['youngs_modulus'], 1), 1.0)
        else:
            ym_sim = 0.5
        factors['youngs_modulus'] = round(ym_sim * 100, 1)
        weighted_sum += ym_sim * 20
        total_weight += 20

        if fp_a['avg_rebound'] > 0 and fp_b['avg_rebound'] > 0:
            rr_diff = abs(fp_a['avg_rebound'] - fp_b['avg_rebound'])
            rr_sim = 1.0 - min(rr_diff / max(fp_a['avg_rebound'], 1), 1.0)
        else:
            rr_sim = 0.5
        factors['rebound_rate'] = round(rr_sim * 100, 1)
        weighted_sum += rr_sim * 15
        total_weight += 15

        if fp_a['material_source'] == fp_b['material_source']:
            src_sim = 1.0
        else:
            src_sim = 0.5
        factors['material_source'] = round(src_sim * 100, 1)
        weighted_sum += src_sim * 10
        total_weight += 10

        if fp_a['elongation_at_break'] > 0 and fp_b['elongation_at_break'] > 0:
            eb_diff = abs(fp_a['elongation_at_break'] - fp_b['elongation_at_break'])
            eb_sim = 1.0 - min(eb_diff / max(fp_a['elongation_at_break'], 1), 1.0)
        else:
            eb_sim = 0.5
        factors['elongation_at_break'] = round(eb_sim * 100, 1)
        weighted_sum += eb_sim * 10
        total_weight += 10

        similarity = (weighted_sum / total_weight * 100) if total_weight > 0 else 50
        return round(similarity, 1), factors

    def calculate_performance_gain(self, source_pred, target_batch):
        target_pred = self._get_or_create_prediction(target_batch)
        gains = {}

        life_gain = target_pred.life_score - source_pred.life_score
        gains['life_score'] = round(life_gain, 1)

        dur_gain = target_pred.durability_score - source_pred.durability_score
        gains['durability'] = round(dur_gain, 1)

        stab_gain = target_pred.stability_score - source_pred.stability_score
        gains['stability'] = round(stab_gain, 1)

        risk_reduction = source_pred.risk_score - target_pred.risk_score
        gains['risk_reduction'] = round(risk_reduction, 1)

        perf_score = (
            life_gain * 0.4
            + dur_gain * 0.25
            + stab_gain * 0.25
            + risk_reduction * 0.1
        )
        return round(perf_score, 1), gains, target_pred

    def generate_recommendations(self, top_n=5):
        source_broken = self.source_batch.is_broken
        candidates = MaterialBatch.objects.exclude(pk=self.source_batch.pk)
        if source_broken:
            candidates = candidates.exclude(status__in=[
                MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW
            ])

        results = []
        for candidate in candidates:
            similarity, sim_factors = self.calculate_similarity(self.source_batch, candidate)
            perf_score, gains, target_pred = self.calculate_performance_gain(
                self.source_pred, candidate
            )
            overall = round(
                similarity * self.WEIGHT_SIMILARITY
                + (perf_score + 50) * self.WEIGHT_PERFORMANCE,
                1
            )

            advantages = []
            if gains['life_score'] > 5:
                advantages.append(f'寿命评分提高{gains["life_score"]:.1f}分')
            if gains['durability'] > 5:
                advantages.append(f'耐久性提升{gains["durability"]:.1f}分')
            if gains['stability'] > 5:
                advantages.append(f'稳定性提升{gains["stability"]:.1f}分')
            if gains['risk_reduction'] > 10:
                advantages.append(f'风险指数降低{gains["risk_reduction"]:.1f}')
            if candidate.status == MaterialBatch.STATUS_ACTIVE and source_broken:
                advantages.append('状态正常，可直接使用')

            caveats = []
            if gains['life_score'] < -5:
                caveats.append(f'寿命评分下降{gains["life_score"]:.1f}分')
            if gains['durability'] < -5:
                caveats.append(f'耐久性下降{gains["durability"]:.1f}分')
            if similarity < 60:
                caveats.append('材料属性相似度较低，可能需要调整工艺')

            rec, created = MaterialRecommendation.objects.update_or_create(
                source_batch=self.source_batch,
                recommended_batch=candidate,
                defaults={
                    'similarity_score': similarity,
                    'performance_score': perf_score,
                    'overall_score': overall,
                    'similarity_factors': sim_factors,
                    'advantages': advantages,
                    'caveats': caveats,
                }
            )
            results.append({
                'recommendation': rec,
                'gains': gains,
                'target_prediction': target_pred,
            })

        results.sort(key=lambda x: x['recommendation'].overall_score, reverse=True)
        return results[:top_n]


class BowTypeMatcher:
    def __init__(self, batch):
        self.batch = batch
        self.prediction = LifePrediction.objects.filter(batch=batch, is_latest=True).first()
        if self.prediction is None:
            predictor = LifePredictor(batch)
            result = predictor.predict()
            self.prediction = result['prediction']

    def match_bow_type(self, bow_type):
        criteria = {}
        score = 0.0
        max_score = 0.0

        diam_min = bow_type.recommended_diameter_min
        diam_max = bow_type.recommended_diameter_max
        if diam_min <= self.batch.diameter <= diam_max:
            d_score = 20
            criteria['diameter'] = {'result': 'pass', 'message': f'直径{self.batch.diameter}mm符合范围[{diam_min}-{diam_max}]', 'score': 20}
        else:
            diff = min(abs(self.batch.diameter - diam_min), abs(self.batch.diameter - diam_max))
            ratio = 1.0 - min(diff / max(diam_min, 0.01), 1.0)
            d_score = round(20 * ratio, 1)
            criteria['diameter'] = {'result': 'partial', 'message': f'直径{self.batch.diameter}mm偏离推荐范围[{diam_min}-{diam_max}]', 'score': d_score}
        score += d_score
        max_score += 20

        tensile = self.batch.tensile_strength or 0
        min_ts = bow_type.min_tensile_strength
        if tensile >= min_ts:
            ts_score = 30
            criteria['tensile_strength'] = {'result': 'pass', 'message': f'抗拉强度{tensile:.0f}MPa达到要求≥{min_ts}MPa', 'score': 30}
        else:
            ratio = tensile / min_ts if min_ts > 0 else 0
            ts_score = round(30 * ratio, 1)
            criteria['tensile_strength'] = {'result': 'fail', 'message': f'抗拉强度{tensile:.0f}MPa低于要求≥{min_ts}MPa', 'score': ts_score}
        score += ts_score
        max_score += 30

        cycles = self.batch.fatigue_cycles_to_failure or 0
        min_cycles = bow_type.min_fatigue_cycles
        if cycles >= min_cycles:
            fc_score = 25
            criteria['fatigue_cycles'] = {'result': 'pass', 'message': f'断裂循环{cycles}次达到要求≥{min_cycles}次', 'score': 25}
        else:
            ratio = cycles / min_cycles if min_cycles > 0 else 0
            fc_score = round(25 * min(ratio * 1.5, 1.0), 1)
            criteria['fatigue_cycles'] = {'result': 'partial', 'message': f'断裂循环{cycles}次接近要求≥{min_cycles}次', 'score': fc_score}
        score += fc_score
        max_score += 25

        life = self.prediction.life_score
        if life >= 80:
            life_score = 15
        elif life >= 60:
            life_score = 10
        elif life >= 40:
            life_score = 5
        else:
            life_score = 2
        criteria['life_score'] = {'result': 'pass' if life >= 60 else 'partial', 'message': f'综合寿命评分{life:.1f}', 'score': life_score}
        score += life_score
        max_score += 15

        max_force = self.batch.max_tension_force or 0
        min_draw_n = bow_type.min_draw_force_newtons
        max_draw_n = bow_type.max_draw_force_newtons
        if max_force >= min_draw_n * 1.5:
            sf_score = 10
            criteria['safety_factor'] = {'result': 'pass', 'message': f'最大拉力{max_force:.0f}N满足安全系数要求', 'score': 10}
        elif max_force >= min_draw_n:
            sf_score = 5
            criteria['safety_factor'] = {'result': 'partial', 'message': f'最大拉力{max_force:.0f}N安全系数偏低', 'score': 5}
        else:
            sf_score = 1
            criteria['safety_factor'] = {'result': 'fail', 'message': f'最大拉力{max_force:.0f}N可能不满足{bow_type.name}拉力要求', 'score': 1}
        score += sf_score
        max_score += 10

        match_score = round((score / max_score) * 100, 1) if max_score > 0 else 0

        if match_score >= 85:
            match_level = BowTypeMatching.MATCH_LEVEL_EXCELLENT
        elif match_score >= 70:
            match_level = BowTypeMatching.MATCH_LEVEL_GOOD
        elif match_score >= 50:
            match_level = BowTypeMatching.MATCH_LEVEL_FAIR
        else:
            match_level = BowTypeMatching.MATCH_LEVEL_POOR

        notes_parts = []
        for k, v in criteria.items():
            if v['result'] != 'pass':
                notes_parts.append(v['message'])
        notes = '; '.join(notes_parts) if notes_parts else '各项指标均达到推荐要求'

        matching, created = BowTypeMatching.objects.update_or_create(
            batch=self.batch,
            bow_type=bow_type,
            defaults={
                'match_level': match_level,
                'match_score': match_score,
                'criteria_results': criteria,
                'notes': notes,
            }
        )
        return matching

    def match_all_bow_types(self):
        bow_types = BowType.objects.all()
        results = []
        for bt in bow_types:
            matching = self.match_bow_type(bt)
            results.append(matching)
        results.sort(key=lambda x: x.match_score, reverse=True)
        return results


class BatchRanker:
    def __init__(self):
        pass

    def _get_latest_prediction(self, batch):
        return LifePrediction.objects.filter(batch=batch, is_latest=True).first()

    def _ensure_predictions(self, batches):
        for batch in batches:
            if not self._get_latest_prediction(batch):
                try:
                    predictor = LifePredictor(batch)
                    predictor.predict()
                except Exception:
                    pass

    def calculate_lifetime_score(self, batch):
        pred = self._get_latest_prediction(batch)
        if not pred:
            return 0.0
        cycles = pred.predicted_cycles_to_failure or 0
        hours = pred.predicted_lifetime_hours or 0
        life_score = pred.life_score
        return round(
            life_score * 0.5
            + min(cycles / 1000, 100) * 0.3
            + min(hours / 50, 100) * 0.2,
            1
        )

    def calculate_durability_score(self, batch):
        pred = self._get_latest_prediction(batch)
        if not pred:
            return 0.0
        tensile = batch.tensile_strength or 0
        cycles = batch.fatigue_cycles_to_failure or 0
        return round(
            pred.durability_score * 0.5
            + min(tensile / 10, 100) * 0.3
            + min(cycles / 1000, 100) * 0.2,
            1
        )

    def calculate_stability_score(self, batch):
        pred = self._get_latest_prediction(batch)
        if not pred:
            return 0.0
        avg_rebound = batch.avg_rebound_rate or 0
        anomaly_penalty = min(batch.anomaly_count * 5, 30)
        return round(
            max(0, pred.stability_score * 0.6 + avg_rebound * 0.4 - anomaly_penalty),
            1
        )

    def calculate_performance_score(self, batch):
        tensile = batch.tensile_strength or 0
        youngs = batch.youngs_modulus or 0
        elong = batch.elongation_at_break or 0
        max_force = batch.max_tension_force or 0
        return round(
            min(tensile / 10, 100) * 0.3
            + min(youngs / 200, 100) * 0.2
            + min(elong / 0.3, 100) * 0.2
            + min(max_force / 10, 100) * 0.3,
            1
        )

    def calculate_overall_score(self, batch):
        pred = self._get_latest_prediction(batch)
        if not pred:
            return 0.0
        return round(
            self.calculate_lifetime_score(batch) * 0.25
            + self.calculate_durability_score(batch) * 0.25
            + self.calculate_stability_score(batch) * 0.25
            + self.calculate_performance_score(batch) * 0.25,
            1
        )

    def generate_rankings(self, ranking_type=None):
        batches = MaterialBatch.objects.all()
        self._ensure_predictions(batches)

        type_map = {
            BatchRanking.RANKING_TYPE_LIFETIME: self.calculate_lifetime_score,
            BatchRanking.RANKING_TYPE_DURABILITY: self.calculate_durability_score,
            BatchRanking.RANKING_TYPE_STABILITY: self.calculate_stability_score,
            BatchRanking.RANKING_TYPE_PERFORMANCE: self.calculate_performance_score,
            BatchRanking.RANKING_TYPE_OVERALL: self.calculate_overall_score,
        }

        if ranking_type:
            types_to_run = [ranking_type]
        else:
            types_to_run = list(type_map.keys())

        all_rankings = []
        for rt in types_to_run:
            calc_fn = type_map[rt]
            scored = []
            for batch in batches:
                try:
                    score = calc_fn(batch)
                    scored.append((batch, score))
                except Exception:
                    continue
            scored.sort(key=lambda x: x[1], reverse=True)

            BatchRanking.objects.filter(ranking_type=rt).delete()
            for rank, (batch, score) in enumerate(scored, 1):
                ranking = BatchRanking.objects.create(
                    batch=batch,
                    ranking_type=rt,
                    rank=rank,
                    score=score,
                )
                all_rankings.append(ranking)

        return all_rankings

    def get_rankings(self, ranking_type, limit=20):
        existing = BatchRanking.objects.filter(ranking_type=ranking_type).count()
        if existing == 0:
            self.generate_rankings(ranking_type)
        qs = BatchRanking.objects.filter(
            ranking_type=ranking_type
        ).select_related('batch').order_by('rank')
        return list(qs[:limit])


class RecipePredictor:
    WEIGHT_DURABILITY = 0.30
    WEIGHT_STABILITY = 0.25
    WEIGHT_REBOUND = 0.20
    WEIGHT_STRENGTH = 0.25

    BENCHMARK_TWIST = 120
    BENCHMARK_STRAND = 16
    BENCHMARK_CURING_TEMP = 60
    BENCHMARK_CURING_HOURS = 24

    def __init__(self, recipe):
        self.recipe = recipe
        self.analyzer = StatisticsAnalyzer()

    def _evaluate_twist_factor(self):
        score = 50.0
        factors = []
        if self.recipe.twist_count is None:
            return 50.0, ['捻度未设置，使用基准值评估']
        diff = abs(self.recipe.twist_count - self.BENCHMARK_TWIST)
        ratio = 1.0 - min(diff / self.BENCHMARK_TWIST, 1.0)
        twist_score = ratio * 50
        score += twist_score
        if self.recipe.twist_count < self.BENCHMARK_TWIST * 0.7:
            factors.append(f'捻度{self.recipe.twist_count}偏低，可能降低耐久性')
        elif self.recipe.twist_count > self.BENCHMARK_TWIST * 1.3:
            factors.append(f'捻度{self.recipe.twist_count}偏高，可能影响回弹')
        else:
            factors.append(f'捻度{self.recipe.twist_count}处于合理范围')
        return min(score, 100), factors

    def _evaluate_strand_factor(self):
        score = 50.0
        factors = []
        if self.recipe.strand_count is None:
            return 50.0, ['股数未设置，使用基准值评估']
        diff = abs(self.recipe.strand_count - self.BENCHMARK_STRAND)
        ratio = 1.0 - min(diff / self.BENCHMARK_STRAND, 1.0)
        strand_score = ratio * 50
        score += strand_score
        if self.recipe.strand_count < self.BENCHMARK_STRAND * 0.6:
            factors.append(f'股数{self.recipe.strand_count}偏少，强度可能不足')
        elif self.recipe.strand_count > self.BENCHMARK_STRAND * 1.5:
            factors.append(f'股数{self.recipe.strand_count}偏多，可能降低回弹速度')
        else:
            factors.append(f'股数{self.recipe.strand_count}配置合理')
        return min(score, 100), factors

    def _evaluate_curing_factor(self):
        score = 50.0
        factors = []
        temp_ok = False
        dur_ok = False
        if self.recipe.curing_temperature is not None:
            temp_diff = abs(self.recipe.curing_temperature - self.BENCHMARK_CURING_TEMP)
            temp_ratio = 1.0 - min(temp_diff / self.BENCHMARK_CURING_TEMP, 1.0)
            score += temp_ratio * 25
            if 40 <= self.recipe.curing_temperature <= 80:
                temp_ok = True
                factors.append(f'固化温度{self.recipe.curing_temperature}°C合理')
            else:
                factors.append(f'固化温度{self.recipe.curing_temperature}°C偏离推荐范围')
        if self.recipe.curing_duration is not None:
            dur_diff = abs(self.recipe.curing_duration - self.BENCHMARK_CURING_HOURS)
            dur_ratio = 1.0 - min(dur_diff / self.BENCHMARK_CURING_HOURS, 1.0)
            score += dur_ratio * 25
            if 12 <= self.recipe.curing_duration <= 48:
                dur_ok = True
                factors.append(f'固化时间{self.recipe.curing_duration}h合理')
            else:
                factors.append(f'固化时间{self.recipe.curing_duration}h偏离推荐范围')
        if temp_ok and dur_ok:
            factors.append('固化工艺配置良好')
        return min(score, 100), factors

    def _evaluate_material_factor(self):
        score = 50.0
        factors = []
        if not self.recipe.base_material:
            return 50.0, ['基础材料未指定']
        premium_materials = ['蚕丝', '凯夫拉', 'dyneema', 'spectra', '超高分子量聚乙烯']
        mid_materials = ['麻', '尼龙', '涤纶']
        material_lower = self.recipe.base_material.lower()
        matched = False
        for m in premium_materials:
            if m.lower() in material_lower:
                score = 90.0
                factors.append(f'基础材料{self.recipe.base_material}为高性能材料')
                matched = True
                break
        if not matched:
            for m in mid_materials:
                if m.lower() in material_lower:
                    score = 70.0
                    factors.append(f'基础材料{self.recipe.base_material}为中等性能材料')
                    matched = True
                    break
        if not matched:
            factors.append(f'基础材料{self.recipe.base_material}性能待验证')
        return min(score, 100), factors

    def _evaluate_process_params(self):
        score = 50.0
        factors = []
        critical_params = self.recipe.params.filter(is_critical=True)
        if critical_params.exists():
            param_scores = []
            for p in critical_params:
                if p.min_value is not None and p.max_value is not None and p.max_value > p.min_value:
                    mid = (p.min_value + p.max_value) / 2
                    span = p.max_value - p.min_value
                    if span > 0:
                        deviation = abs(p.param_value - mid) / (span / 2)
                        p_score = max(0, (1.0 - deviation) * 100)
                        param_scores.append(p_score)
                        if deviation < 0.2:
                            factors.append(f'关键参数{p.param_name}={p.param_value}处于最佳区间')
                        elif deviation < 0.5:
                            factors.append(f'关键参数{p.param_name}={p.param_value}偏离最优值')
                        else:
                            factors.append(f'关键参数{p.param_name}={p.param_value}偏离较大')
            if param_scores:
                avg_param = sum(param_scores) / len(param_scores)
                score = avg_param * 0.5 + 50
        return min(score, 100), factors

    def _evaluate_reference_trials(self):
        trial_results = TrialResult.objects.filter(
            trial_plan__recipe=self.recipe
        )
        if not trial_results.exists():
            return None, [], []
        durabilities = list(trial_results.filter(durability_score__isnull=False).values_list('durability_score', flat=True))
        stabilities = list(trial_results.filter(stability_score__isnull=False).values_list('stability_score', flat=True))
        rebounds = list(trial_results.filter(rebound_performance__isnull=False).values_list('rebound_performance', flat=True))
        strengths = list(trial_results.filter(strength_score__isnull=False).values_list('strength_score', flat=True))
        reference = []
        for tr in trial_results[:5]:
            reference.append({
                'trial_code': tr.trial_plan.plan_code,
                'sample': tr.sample_id,
                'overall': tr.overall_score,
                'risk_level': tr.risk_level,
            })
        avg_data = {
            'durability': round(sum(durabilities) / len(durabilities), 1) if durabilities else None,
            'stability': round(sum(stabilities) / len(stabilities), 1) if stabilities else None,
            'rebound': round(sum(rebounds) / len(rebounds), 1) if rebounds else None,
            'strength': round(sum(strengths) / len(strengths), 1) if strengths else None,
            'trial_count': trial_results.count(),
        }
        return avg_data, reference, ['基于' + str(trial_results.count()) + '次历史试制数据评估']

    def predict(self):
        all_factors = []
        strengths = []
        weaknesses = []
        ref_data, refs, ref_factors = self._evaluate_reference_trials()
        all_factors.extend(ref_factors)

        twist_score, twist_factors = self._evaluate_twist_factor()
        strand_score, strand_factors = self._evaluate_strand_factor()
        curing_score, curing_factors = self._evaluate_curing_factor()
        material_score, material_factors = self._evaluate_material_factor()
        param_score, param_factors = self._evaluate_process_params()

        all_factors.extend(twist_factors + strand_factors + curing_factors + material_factors + param_factors)

        if ref_data:
            predicted_durability = round(ref_data.get('durability') or (
                twist_score * 0.35 + strand_score * 0.35 + curing_score * 0.15 + material_score * 0.15
            ), 1)
            predicted_stability = round(ref_data.get('stability') or (
                twist_score * 0.25 + param_score * 0.35 + curing_score * 0.20 + material_score * 0.20
            ), 1)
            predicted_rebound = round(ref_data.get('rebound') or (
                twist_score * 0.40 + strand_score * 0.25 + material_score * 0.20 + param_score * 0.15
            ), 1)
            predicted_strength = round(ref_data.get('strength') or (
                strand_score * 0.40 + material_score * 0.35 + twist_score * 0.15 + curing_score * 0.10
            ), 1)
        else:
            predicted_durability = round(
                twist_score * 0.35 + strand_score * 0.35 + curing_score * 0.15 + material_score * 0.15, 1
            )
            predicted_stability = round(
                twist_score * 0.25 + param_score * 0.35 + curing_score * 0.20 + material_score * 0.20, 1
            )
            predicted_rebound = round(
                twist_score * 0.40 + strand_score * 0.25 + material_score * 0.20 + param_score * 0.15, 1
            )
            predicted_strength = round(
                strand_score * 0.40 + material_score * 0.35 + twist_score * 0.15 + curing_score * 0.10, 1
            )

        predicted_overall = round(
            predicted_durability * self.WEIGHT_DURABILITY
            + predicted_stability * self.WEIGHT_STABILITY
            + predicted_rebound * self.WEIGHT_REBOUND
            + predicted_strength * self.WEIGHT_STRENGTH, 1
        )

        low_scores = []
        high_scores = []
        for label, val in [('耐久性', predicted_durability), ('稳定性', predicted_stability),
                           ('回弹表现', predicted_rebound), ('强度', predicted_strength)]:
            if val >= 80:
                high_scores.append(label)
            elif val < 50:
                low_scores.append(label)
        if high_scores:
            strengths.append('优势指标：' + '、'.join(high_scores))
        if low_scores:
            weaknesses.append('待改进指标：' + '、'.join(low_scores))

        if twist_score >= 75:
            strengths.append('捻度配置合理，有利于性能平衡')
        elif twist_score < 50:
            weaknesses.append('捻度配置需要优化')
        if material_score >= 80:
            strengths.append('基础材料性能优异')
        elif material_score < 55:
            weaknesses.append('基础材料性能有待提升，可考虑更换材料')
        if curing_score >= 70:
            strengths.append('固化工艺参数配置良好')
        elif curing_score < 50:
            weaknesses.append('固化工艺需要优化温度或时长')
        if param_score >= 75 and self.recipe.params.filter(is_critical=True).exists():
            strengths.append('关键工艺参数控制精准')
        elif param_score < 50 and self.recipe.params.filter(is_critical=True).exists():
            weaknesses.append('关键工艺参数偏离最优区间')

        predicted_risk_score = round(max(0, 100 - predicted_overall), 1)
        if predicted_risk_score >= 75:
            predicted_risk_level = RecipePrediction.RISK_LEVEL_CRITICAL
        elif predicted_risk_score >= 50:
            predicted_risk_level = RecipePrediction.RISK_LEVEL_HIGH
        elif predicted_risk_score >= 25:
            predicted_risk_level = RecipePrediction.RISK_LEVEL_MEDIUM
        else:
            predicted_risk_level = RecipePrediction.RISK_LEVEL_LOW

        optimization_suggestions = self._generate_optimization_suggestions(
            predicted_durability, predicted_stability, predicted_rebound, predicted_strength,
            twist_score, strand_score, curing_score, material_score, param_score, weaknesses
        )

        predicted_lifespan = None
        if predicted_overall > 0:
            base_hours = 200
            predicted_lifespan = round(base_hours * (predicted_overall / 100) * 1.5, 1)

        confidence = 0.5
        if ref_data and ref_data.get('trial_count', 0) >= 3:
            confidence = 0.85
        elif ref_data and ref_data.get('trial_count', 0) >= 1:
            confidence = 0.7
        elif self.recipe.params.count() >= 5:
            confidence = 0.6

        prediction = RecipePrediction.objects.create(
            recipe=self.recipe,
            predicted_durability=predicted_durability,
            predicted_stability=predicted_stability,
            predicted_rebound=predicted_rebound,
            predicted_strength=predicted_strength,
            predicted_overall=predicted_overall,
            predicted_risk_level=predicted_risk_level,
            predicted_risk_score=predicted_risk_score,
            predicted_lifespan_hours=predicted_lifespan,
            confidence_level=confidence,
            key_factors=all_factors,
            strength_analysis=strengths,
            weakness_analysis=weaknesses,
            optimization_suggestions=optimization_suggestions,
            prediction_method='hybrid_rule_and_history_based',
            reference_trials=refs,
        )
        return {
            'prediction': prediction,
            'component_scores': {
                'twist': twist_score,
                'strand': strand_score,
                'curing': curing_score,
                'material': material_score,
                'params': param_score,
            },
            'reference_data': ref_data,
        }

    def _generate_optimization_suggestions(self, dur, stab, reb, str_, twist, strand, curing, material, params, weaknesses):
        suggestions = []
        if dur < 60:
            if twist < 60:
                suggestions.append({
                    'category': 'parameter',
                    'severity': 'high' if dur < 45 else 'medium',
                    'title': '优化捻度配置提升耐久性',
                    'description': f'当前捻度评分{twist:.1f}偏低，建议调整捻度至{self.BENCHMARK_TWIST}±20%范围内，可提升纤维抱合力和耐磨性能。',
                    'expected': {'durability': 10, 'stability': 5},
                })
            if strand < 60:
                suggestions.append({
                    'category': 'parameter',
                    'severity': 'high' if strand < 45 else 'medium',
                    'title': '调整股数配置',
                    'description': f'当前股数评分{strand:.1f}，建议股数设置在{self.BENCHMARK_STRAND}±4股范围内，平衡强度与柔韧性。',
                    'expected': {'durability': 8, 'strength': 12},
                })
        if stab < 60:
            if curing < 60:
                suggestions.append({
                    'category': 'process',
                    'severity': 'medium',
                    'title': '优化固化工艺提升稳定性',
                    'description': f'固化工艺评分{curing:.1f}偏低，建议温度设为{self.BENCHMARK_CURING_TEMP}°C左右，时长{self.BENCHMARK_CURING_HOURS}h，使材料结构充分稳定。',
                    'expected': {'stability': 12, 'durability': 5},
                })
            if params < 60 and self.recipe.params.filter(is_critical=True).exists():
                suggestions.append({
                    'category': 'parameter',
                    'severity': 'medium',
                    'title': '校准关键工艺参数',
                    'description': '关键工艺参数偏离最优区间，建议对照参数容差范围进行精确调整。',
                    'expected': {'stability': 10, 'rebound': 5},
                })
        if reb < 60:
            if twist < 65:
                suggestions.append({
                    'category': 'parameter',
                    'severity': 'medium',
                    'title': '微调捻度改善回弹',
                    'description': '捻度对回弹性能影响显著，建议在保证耐久性的前提下适度调整捻度。',
                    'expected': {'rebound': 10, 'stability': 3},
                })
            if self.recipe.coating_material:
                suggestions.append({
                    'category': 'material',
                    'severity': 'low',
                    'title': '优化涂层材料',
                    'description': '可考虑使用低摩擦系数涂层材料，减少内部摩擦损耗，提升回弹效率。',
                    'expected': {'rebound': 6},
                })
        if str_ < 60:
            if material < 60:
                suggestions.append({
                    'category': 'material',
                    'severity': 'high' if str_ < 45 else 'medium',
                    'title': '考虑升级基础材料',
                    'description': f'当前材料评分{material:.1f}，可考虑选用高强度纤维材料（如超高分子量聚乙烯、芳纶等）。',
                    'expected': {'strength': 15, 'durability': 8},
                })
            if strand < 60:
                suggestions.append({
                    'category': 'parameter',
                    'severity': 'medium',
                    'title': '增加股数提升强度',
                    'description': '在弓弦直径允许范围内适当增加股数，可有效提升整体抗拉强度。',
                    'expected': {'strength': 10},
                })
        if not suggestions:
            suggestions.append({
                'category': 'other',
                'severity': 'low',
                'title': '当前配方综合表现良好',
                'description': '各项指标均处于较好水平，建议进行小批量试制验证实际表现。',
                'expected': {},
            })
        return suggestions


class RecipeComparator:
    def __init__(self, recipes):
        self.recipes = recipes

    def _ensure_predictions(self):
        for recipe in self.recipes:
            if not recipe.latest_prediction:
                try:
                    predictor = RecipePredictor(recipe)
                    predictor.predict()
                except Exception:
                    pass

    def compare_performance(self):
        self._ensure_predictions()
        result = {
            'recipes': [],
            'best_in_category': {},
            'radar_data': {},
            'recommendations': [],
        }
        categories = ['durability', 'stability', 'rebound', 'strength', 'overall']
        cat_labels = {
            'durability': '耐久性',
            'stability': '稳定性',
            'rebound': '回弹表现',
            'strength': '强度',
            'overall': '综合评分',
        }
        best_scores = {c: (None, None) for c in categories}
        worst_risk = (None, 101)

        for recipe in self.recipes:
            pred = recipe.latest_prediction
            perf = recipe.get_performance_summary()
            data = {
                'id': recipe.id,
                'code': recipe.recipe_code,
                'name': recipe.recipe_name,
                'type': recipe.get_recipe_type_display(),
                'status': recipe.get_status_display(),
                'predicted': pred.get_prediction_dict() if pred else None,
                'actual': perf,
                'trial_count': recipe.trial_count,
                'param_count': recipe.param_count,
            }
            if pred:
                for c in categories:
                    key = c if c != 'overall' else 'overall'
                    val = getattr(pred, f'predicted_{c}', None) if c != 'overall' else pred.predicted_overall
                    if val is not None:
                        if best_scores[c][1] is None or val > best_scores[c][1]:
                            best_scores[c] = (recipe.recipe_code, val)
                if pred.predicted_risk_score < worst_risk[1]:
                    worst_risk = (recipe.recipe_code, pred.predicted_risk_score)
            result['recipes'].append(data)

        result['best_in_category'] = {
            cat_labels[k]: {'recipe': v[0], 'score': v[1]}
            for k, v in best_scores.items() if v[0] is not None
        }
        result['lowest_risk'] = {'recipe': worst_risk[0], 'risk_score': worst_risk[1]}

        radar_categories = ['durability', 'stability', 'rebound', 'strength']
        radar_labels = [cat_labels[c] for c in radar_categories]
        radar_datasets = []
        for recipe in self.recipes:
            pred = recipe.latest_prediction
            if pred:
                radar_datasets.append({
                    'label': recipe.recipe_code,
                    'data': [
                        pred.predicted_durability,
                        pred.predicted_stability,
                        pred.predicted_rebound,
                        pred.predicted_strength or 0,
                    ],
                })
        result['radar_data'] = {
            'labels': radar_labels,
            'datasets': radar_datasets,
        }

        overall_scores = []
        for recipe in self.recipes:
            pred = recipe.latest_prediction
            if pred:
                overall_scores.append((recipe, pred.predicted_overall))
        overall_scores.sort(key=lambda x: x[1], reverse=True)
        if len(overall_scores) >= 2:
            best_recipe, best_score = overall_scores[0]
            second_recipe, second_score = overall_scores[1]
            diff = best_score - second_score
            if diff >= 10:
                result['recommendations'].append(
                    f'配方{best_recipe.recipe_code}综合评分领先{diff:.1f}分，优势明显，推荐优先试制'
                )
            else:
                result['recommendations'].append(
                    f'配方{best_recipe.recipe_code}与{second_recipe.recipe_code}综合评分接近（差距{diff:.1f}分），建议并行试制对比实际表现'
                )
        if result.get('lowest_risk', {}).get('recipe'):
            low_risk_recipe = result['lowest_risk']['recipe']
            if overall_scores and low_risk_recipe != overall_scores[0][0].recipe_code:
                result['recommendations'].append(
                    f'配方{low_risk_recipe}风险等级最低，适合对可靠性要求高的应用场景'
                )
        return result

    def compare_parameters(self):
        result = {
            'recipes': [],
            'param_matrix': {},
            'differences': [],
        }
        all_param_names = set()
        for recipe in self.recipes:
            for p in recipe.params.all():
                all_param_names.add(p.param_name)
        core_attrs = [
            ('base_material', '基础材料', None),
            ('twist_count', '捻度(捻/m)', None),
            ('strand_count', '股数', None),
            ('coating_material', '涂层材料', None),
            ('curing_method', '固化方式', None),
            ('curing_temperature', '固化温度(°C)', None),
            ('curing_duration', '固化时间(h)', None),
            ('twist_direction', '捻向', None),
            ('weaving_method', '编织方式', None),
        ]
        for attr, label, _ in core_attrs:
            values = []
            for recipe in self.recipes:
                v = getattr(recipe, attr, None)
                values.append((recipe.recipe_code, v))
            distinct_vals = set(str(v[1]) for v in values if v[1] is not None)
            if len(distinct_vals) > 1:
                result['differences'].append(f'{label}存在差异：' + '、'.join(distinct_vals))
        for recipe in self.recipes:
            data = {
                'id': recipe.id,
                'code': recipe.recipe_code,
                'name': recipe.recipe_name,
                'core_attrs': {},
                'params': {},
            }
            for attr, label, _ in core_attrs:
                data['core_attrs'][label] = getattr(recipe, attr, None)
            for p in recipe.params.all():
                data['params'][p.param_name] = {
                    'value': p.param_value,
                    'unit': p.param_unit,
                    'type': p.get_param_type_display(),
                    'critical': p.is_critical,
                }
            result['recipes'].append(data)
        return result

    def full_comparison(self):
        perf = self.compare_performance()
        params = self.compare_parameters()
        return {
            'performance': perf,
            'parameters': params,
            'summary': {
                'recipe_count': len(self.recipes),
                'best_overall': perf.get('best_in_category', {}).get('综合评分', {}),
                'param_differences_count': len(params.get('differences', [])),
            },
        }


class OptimizationGenerator:
    def __init__(self, recipe, trial_result=None):
        self.recipe = recipe
        self.trial_result = trial_result

    def generate_from_prediction(self):
        predictor = RecipePredictor(self.recipe)
        pred_result = predictor.predict()
        prediction = pred_result['prediction']
        suggestions = []
        for sug in prediction.optimization_suggestions:
            severity_map = {
                'critical': OptimizationSuggestion.SEVERITY_CRITICAL,
                'high': OptimizationSuggestion.SEVERITY_HIGH,
                'medium': OptimizationSuggestion.SEVERITY_MEDIUM,
                'low': OptimizationSuggestion.SEVERITY_LOW,
            }
            category_map = {
                'parameter': OptimizationSuggestion.CATEGORY_PARAMETER,
                'material': OptimizationSuggestion.CATEGORY_MATERIAL,
                'process': OptimizationSuggestion.CATEGORY_PROCESS,
                'testing': OptimizationSuggestion.CATEGORY_TESTING,
                'other': OptimizationSuggestion.CATEGORY_OTHER,
            }
            sug_obj = OptimizationSuggestion.objects.create(
                recipe=self.recipe,
                trial_result=self.trial_result,
                title=sug.get('title', '优化建议'),
                category=category_map.get(sug.get('category'), OptimizationSuggestion.CATEGORY_OTHER),
                severity=severity_map.get(sug.get('severity'), OptimizationSuggestion.SEVERITY_MEDIUM),
                description=sug.get('description', ''),
                suggested_action=sug.get('description', ''),
                expected_improvement=sug.get('expected', {}),
                generated_by='prediction_engine',
            )
            suggestions.append(sug_obj)
        return suggestions

    def generate_from_trial_result(self):
        if not self.trial_result:
            return []
        suggestions = []
        tr = self.trial_result
        targets_missed = tr.targets_missed or []
        for tm in targets_missed:
            category = tm.get('category', 'other')
            actual = tm.get('actual', 0)
            target = tm.get('target', 0)
            gap = target - actual if tm.get('mandatory', True) else 0
            if category == 'durability':
                suggestions.append({
                    'title': f'耐久性未达目标（实际{actual}，目标≥{target}）',
                    'category': OptimizationSuggestion.CATEGORY_PARAMETER,
                    'severity': OptimizationSuggestion.SEVERITY_HIGH if tm.get('mandatory') else OptimizationSuggestion.SEVERITY_MEDIUM,
                    'description': f'耐久性评分{actual}低于目标{target}，差距{gap:.1f}分，建议重点优化捻度和股数配置。',
                    'expected': {'durability': gap},
                })
            elif category == 'stability':
                suggestions.append({
                    'title': f'稳定性未达目标（实际{actual}，目标≥{target}）',
                    'category': OptimizationSuggestion.CATEGORY_PROCESS,
                    'severity': OptimizationSuggestion.SEVERITY_HIGH if tm.get('mandatory') else OptimizationSuggestion.SEVERITY_MEDIUM,
                    'description': f'稳定性评分{actual}低于目标{target}，建议优化固化工艺和关键参数控制。',
                    'expected': {'stability': gap},
                })
            elif category == 'rebound':
                suggestions.append({
                    'title': f'回弹表现未达目标（实际{actual}，目标≥{target}）',
                    'category': OptimizationSuggestion.CATEGORY_PARAMETER,
                    'severity': OptimizationSuggestion.SEVERITY_MEDIUM,
                    'description': f'回弹表现{actual}低于目标{target}，可调整捻度或优化涂层材料。',
                    'expected': {'rebound': gap},
                })
            elif category == 'strength':
                suggestions.append({
                    'title': f'强度未达目标（实际{actual}，目标≥{target}）',
                    'category': OptimizationSuggestion.CATEGORY_MATERIAL,
                    'severity': OptimizationSuggestion.SEVERITY_HIGH if tm.get('mandatory') else OptimizationSuggestion.SEVERITY_MEDIUM,
                    'description': f'强度评分{actual}低于目标{target}，建议增加股数或升级材料。',
                    'expected': {'strength': gap},
                })
        if tr.is_broken:
            suggestions.append({
                'title': '试制过程发生断裂',
                'category': OptimizationSuggestion.CATEGORY_PROCESS,
                'severity': OptimizationSuggestion.SEVERITY_CRITICAL,
                'description': f'断裂位置：{tr.break_location or "未记录"}，断裂模式：{tr.break_mode or "未记录"}，原因：{tr.break_reason or "待分析"}。建议全面排查工艺参数并降低测试载荷等级。',
                'expected': {},
            })
        if tr.issues_found:
            suggestions.append({
                'title': '解决试制中发现的问题',
                'category': OptimizationSuggestion.CATEGORY_OTHER,
                'severity': OptimizationSuggestion.SEVERITY_MEDIUM,
                'description': tr.issues_found,
                'expected': {},
            })
        created = []
        for sug in suggestions:
            sug_obj = OptimizationSuggestion.objects.create(
                recipe=self.recipe,
                trial_result=self.trial_result,
                title=sug['title'],
                category=sug['category'],
                severity=sug['severity'],
                description=sug['description'],
                current_state=tr.observations or '',
                expected_improvement=sug.get('expected', {}),
                generated_by='trial_analysis',
            )
            created.append(sug_obj)
        return created

    def generate_all(self):
        suggestions = []
        suggestions.extend(self.generate_from_prediction())
        if self.trial_result:
            suggestions.extend(self.generate_from_trial_result())
        return suggestions


class TrialAnalyzer:
    def __init__(self, trial_plan):
        self.trial_plan = trial_plan
        self.recipe = trial_plan.recipe

    def analyze_results(self):
        results = self.trial_plan.results.all()
        if not results.exists():
            return {'status': 'no_data', 'message': '暂无试制结果数据'}
        analysis = {
            'trial_plan': {
                'code': self.trial_plan.plan_code,
                'name': self.trial_plan.plan_name,
                'recipe_code': self.recipe.recipe_code,
                'sample_count': self.trial_plan.sample_count,
                'result_count': results.count(),
            },
            'performance_stats': {},
            'risk_analysis': {},
            'target_achievement': {},
            'consistency_analysis': {},
            'recommendations': [],
        }
        perf_fields = [
            ('durability_score', '耐久性'),
            ('stability_score', '稳定性'),
            ('rebound_performance', '回弹表现'),
            ('strength_score', '强度'),
            ('overall_score', '综合评分'),
        ]
        analyzer = StatisticsAnalyzer()
        for field, label in perf_fields:
            values = list(results.filter(**{f'{field}__isnull': False}).values_list(field, flat=True))
            if values:
                analysis['performance_stats'][label] = analyzer.basic_stats(values)
        risk_counts = {}
        risk_scores = []
        for r in results:
            lvl = r.get_risk_level_display()
            risk_counts[lvl] = risk_counts.get(lvl, 0) + 1
            if r.risk_score is not None:
                risk_scores.append(r.risk_score)
        analysis['risk_analysis'] = {
            'distribution': risk_counts,
            'avg_risk_score': round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else None,
        }
        all_met = []
        all_missed = []
        pass_count = 0
        partial_count = 0
        fail_count = 0
        for r in results:
            all_met.extend(r.targets_met or [])
            all_missed.extend(r.targets_missed or [])
            if r.result_status == TrialResult.RESULT_PASS:
                pass_count += 1
            elif r.result_status == TrialResult.RESULT_PARTIAL:
                partial_count += 1
            elif r.result_status == TrialResult.RESULT_FAIL:
                fail_count += 1
        analysis['target_achievement'] = {
            'pass_count': pass_count,
            'partial_count': partial_count,
            'fail_count': fail_count,
            'total_met_count': len(all_met),
            'total_missed_count': len(all_missed),
            'missed_targets': all_missed[:10],
        }
        if results.count() >= 3:
            consistencies = {}
            for field, label in perf_fields:
                values = list(results.filter(**{f'{field}__isnull': False}).values_list(field, flat=True))
                if len(values) >= 3:
                    mean_v = sum(values) / len(values)
                    if mean_v > 0:
                        var_v = sum((x - mean_v) ** 2 for x in values) / len(values)
                        cv = math.sqrt(var_v) / mean_v
                        consistencies[label] = {
                            'cv': round(cv * 100, 2),
                            'assessment': '优秀' if cv < 0.05 else '良好' if cv < 0.10 else '一般' if cv < 0.20 else '较差',
                        }
            analysis['consistency_analysis'] = consistencies
        broken = results.filter(is_broken=True)
        if broken.exists():
            analysis['recommendations'].append(f'{broken.count()}个试样发生断裂，建议排查断裂原因并优化工艺')
        if fail_count > 0:
            analysis['recommendations'].append(f'{fail_count}个试样未通过目标验证，建议参考生成的优化建议调整参数')
        if partial_count > 0 and fail_count == 0:
            analysis['recommendations'].append(f'{partial_count}个试样部分通过目标，优化后有望全面达标')
        if pass_count == results.count() and not broken.exists():
            analysis['recommendations'].append('所有试样全部通过验证，表现稳定，可考虑扩大试制或批准配方')
        return analysis
