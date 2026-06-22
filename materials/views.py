import json
import math

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)
from django.contrib import messages

from .models import (
    MaterialBatch, TensionTest, FatigueTest, DataAnomalyLog,
    MaterialProcessParam, BreakageFlowRecord, StatisticalSnapshot,
    BowType, LifePrediction, MaterialRecommendation,
    BowTypeMatching, BatchRanking,
    ProcessRecipe, RecipeParam, PerformanceTarget,
    TrialPlan, TrialResult, RecipePrediction,
    RecipeComparison, OptimizationSuggestion,
)
from .forms import (
    MaterialBatchForm, TensionTestForm, FatigueTestForm,
    BatchReviewForm, AnomalyResolveForm, MaterialProcessParamForm,
    ProcessNoteForm,
)
from .utils import (
    AnomalyDetector, StatisticsAnalyzer, ReboundRateCalculator,
    BreakFlowManager, SnapshotGenerator,
    LifePredictor, MaterialRecommender, BowTypeMatcher, BatchRanker,
    RecipePredictor, RecipeComparator, OptimizationGenerator, TrialAnalyzer,
)


class DashboardView(View):
    def get(self, request):
        analyzer = StatisticsAnalyzer()
        global_stats = analyzer.get_global_statistics()

        batches = MaterialBatch.objects.all()
        total_batches = batches.count()
        broken_batches = sum(1 for b in batches if b.is_broken)
        active_batches = total_batches - broken_batches
        total_tension_tests = TensionTest.objects.count()
        total_fatigue_tests = FatigueTest.objects.count()
        total_tests = total_tension_tests + total_fatigue_tests
        unresolved_anomalies = DataAnomalyLog.objects.filter(is_resolved=False).count()
        flagged_tension = TensionTest.objects.filter(is_flagged=True).count()
        flagged_fatigue = FatigueTest.objects.filter(is_flagged=True).count()
        review_batches = batches.filter(status=MaterialBatch.STATUS_REVIEW).count()
        recent_batches = batches[:5]
        recent_tests = TensionTest.objects.all()[:8]
        recent_fatigue_tests = FatigueTest.objects.all()[:8]
        recent_anomalies = DataAnomalyLog.objects.filter(is_resolved=False)[:5]
        recent_flow_records = BreakageFlowRecord.objects.all()[:10]

        status_distribution = {}
        for choice_val, choice_label in MaterialBatch.STATUS_CHOICES:
            status_distribution[choice_val] = {
                'label': choice_label,
                'count': batches.filter(status=choice_val).count()
            }

        context = {
            'total_batches': total_batches,
            'broken_batches': broken_batches,
            'active_batches': active_batches,
            'total_tests': total_tests,
            'total_tension_tests': total_tension_tests,
            'total_fatigue_tests': total_fatigue_tests,
            'unresolved_anomalies': unresolved_anomalies,
            'flagged_data_count': flagged_tension + flagged_fatigue,
            'review_batches': review_batches,
            'recent_batches': recent_batches,
            'recent_tests': recent_tests,
            'recent_fatigue_tests': recent_fatigue_tests,
            'recent_anomalies': recent_anomalies,
            'recent_flow_records': recent_flow_records,
            'status_distribution_json': json.dumps(status_distribution, ensure_ascii=False),
            'trend_data_json': json.dumps(global_stats.get('trend', []), ensure_ascii=False),
            'source_distribution_json': json.dumps(
                global_stats.get('source_distribution', []), ensure_ascii=False
            ),
            'global_summary': global_stats.get('summary', {}),
        }
        return render(request, 'materials/dashboard.html', context)


class MaterialBatchListView(ListView):
    model = MaterialBatch
    template_name = 'materials/batch_list.html'
    context_object_name = 'batches'
    paginate_by = 20

    def get_queryset(self):
        queryset = MaterialBatch.objects.all()
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                batch_number__icontains=q
            ) | queryset.filter(
                material_source__icontains=q
            )
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['status_choices'] = MaterialBatch.STATUS_CHOICES
        return context


class MaterialBatchDetailView(DetailView):
    model = MaterialBatch
    template_name = 'materials/batch_detail.html'
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tests = self.object.tension_tests.order_by('test_time')
        fatigue_tests = self.object.fatigue_tests.order_by('test_time')
        context['tests'] = tests
        context['fatigue_tests'] = fatigue_tests
        context['anomaly_logs'] = self.object.anomaly_logs.order_by('-created_at')
        context['flow_records'] = self.object.flow_records.order_by('-created_at')
        context['process_params'] = self.object.process_params.order_by('param_type', 'param_name')

        analyzer = StatisticsAnalyzer()
        context['comprehensive_stats'] = analyzer.get_batch_comprehensive_stats(self.object)
        context['batch_stats_summary'] = self.object.get_statistics_summary()

        chart_data = []
        for test in tests:
            chart_data.append({
                'x': float(test.elongation),
                'y': float(test.tension_force),
                'broken': test.is_broken,
                'flagged': test.is_flagged,
                'time': test.test_time.strftime('%Y-%m-%d %H:%M'),
                'stress': test.stress,
                'strain': test.strain,
            })
        context['chart_data_json'] = json.dumps(chart_data, ensure_ascii=False)

        stress_strain_data = []
        for test in tests:
            if test.stress is not None and test.strain is not None:
                stress_strain_data.append({
                    'x': float(test.strain),
                    'y': float(test.stress),
                    'broken': test.is_broken,
                    'flagged': test.is_flagged,
                })
        context['stress_strain_json'] = json.dumps(stress_strain_data, ensure_ascii=False)

        fatigue_chart_data = []
        for ft in fatigue_tests:
            fatigue_chart_data.append({
                'x': ft.cycle_count,
                'y': float(ft.load_force),
                'result': ft.result,
                'flagged': ft.is_flagged,
                'time': ft.test_time.strftime('%Y-%m-%d %H:%M'),
                'damage_severity': ft.damage_severity,
            })
        context['fatigue_chart_data_json'] = json.dumps(fatigue_chart_data, ensure_ascii=False)

        rebound_chart_data = []
        rebound_tests = tests.filter(rebound_rate__isnull=False).order_by('test_time')
        for idx, test in enumerate(rebound_tests):
            rebound_chart_data.append({
                'x': idx + 1,
                'y': float(test.rebound_rate),
                'force': float(test.tension_force),
            })
        context['rebound_chart_json'] = json.dumps(rebound_chart_data, ensure_ascii=False)

        return context


class MaterialBatchCreateView(CreateView):
    model = MaterialBatch
    form_class = MaterialBatchForm
    template_name = 'materials/batch_form.html'

    def get_success_url(self):
        messages.success(self.request, '材料批次创建成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.pk})


class MaterialBatchUpdateView(UpdateView):
    model = MaterialBatch
    form_class = MaterialBatchForm
    template_name = 'materials/batch_form.html'

    def get_success_url(self):
        messages.success(self.request, '材料批次更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.pk})


class MaterialBatchDeleteView(DeleteView):
    model = MaterialBatch
    template_name = 'materials/batch_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '材料批次已删除')
        return reverse('materials:batch_list')


class BatchReviewView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        if batch.status not in (MaterialBatch.STATUS_BROKEN, MaterialBatch.STATUS_REVIEW):
            messages.warning(request, '该批次不在审核状态')
            return redirect('materials:batch_detail', pk=batch.pk)
        if batch.status == MaterialBatch.STATUS_BROKEN:
            BreakFlowManager.start_review(batch)
        form = BatchReviewForm()
        context = {
            'batch': batch,
            'form': form,
            'flow_records': batch.flow_records.order_by('-created_at'),
            'breaking_tests': batch.tension_tests.filter(is_broken=True),
            'breaking_fatigue_tests': batch.fatigue_tests.filter(result=FatigueTest.RESULT_BROKEN),
        }
        return render(request, 'materials/batch_review.html', context)

    def post(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        form = BatchReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            review_notes = form.cleaned_data.get('review_notes', '')
            if action == 'archive':
                success, msg = BreakFlowManager.archive_batch(batch, review_notes=review_notes)
                if success:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            elif action == 'reactivate':
                success, msg = BreakFlowManager.reactivate_batch(batch, review_notes=review_notes)
                if success:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            return redirect('materials:batch_detail', pk=batch.pk)
        context = {
            'batch': batch,
            'form': form,
            'flow_records': batch.flow_records.order_by('-created_at'),
        }
        return render(request, 'materials/batch_review.html', context)


class BatchFlowNoteView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        form = ProcessNoteForm()
        context = {
            'batch': batch,
            'form': form,
        }
        return render(request, 'materials/batch_flow_note.html', context)

    def post(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        form = ProcessNoteForm(request.POST)
        if form.is_valid():
            notes = form.cleaned_data['notes']
            operator = form.cleaned_data.get('operator', '')
            batch.record_flow_action(
                action=BreakageFlowRecord.ACTION_NOTE_ADDED,
                notes=notes,
                operator=operator,
            )
            messages.success(request, '流程备注已添加')
            return redirect('materials:batch_detail', pk=batch.pk)
        context = {
            'batch': batch,
            'form': form,
        }
        return render(request, 'materials/batch_flow_note.html', context)


class TensionTestCreateView(CreateView):
    model = TensionTest
    form_class = TensionTestForm
    template_name = 'materials/test_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(MaterialBatch, pk=kwargs['batch_pk'])
        if not self.batch.can_add_test():
            messages.error(request, '该批次样本已断裂或处于审核/归档状态，无法新增测试记录')
            return redirect('materials:batch_detail', pk=self.batch.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.batch
        existing_tests = self.batch.tension_tests.filter(is_flagged=False)
        if existing_tests.exists():
            forces = list(existing_tests.values_list('tension_force', flat=True))
            elongations = list(existing_tests.values_list('elongation', flat=True))
            context['reference_stats'] = {
                'avg_force': round(sum(forces) / len(forces), 2),
                'min_force': min(forces),
                'max_force': max(forces),
                'avg_elongation': round(sum(elongations) / len(elongations), 2),
                'min_elongation': min(elongations),
                'max_elongation': max(elongations),
                'test_count': existing_tests.count(),
            }
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.batch
        return kwargs

    def form_valid(self, form):
        form.instance.batch = self.batch
        response = super().form_valid(form)
        self._check_and_create_anomaly(form.instance)
        return response

    def _check_and_create_anomaly(self, test):
        detector = AnomalyDetector(test.batch)
        anomalies = detector.check_tension_test(test, exclude_pk=test.pk)
        if anomalies:
            detector.create_anomaly_logs(
                anomalies, DataAnomalyLog.SOURCE_TENSION, test.pk
            )

    def get_success_url(self):
        messages.success(self.request, '测试记录添加成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.batch.pk})


class TensionTestUpdateView(UpdateView):
    model = TensionTest
    form_class = TensionTestForm
    template_name = 'materials/test_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.object.batch
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        detector = AnomalyDetector(self.object.batch)
        anomalies = detector.check_tension_test(self.object, exclude_pk=self.object.pk)
        if anomalies:
            detector.create_anomaly_logs(
                anomalies, DataAnomalyLog.SOURCE_TENSION, self.object.pk
            )
        return response

    def get_success_url(self):
        messages.success(self.request, '测试记录更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class TensionTestDeleteView(DeleteView):
    model = TensionTest
    template_name = 'materials/test_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '测试记录已删除')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class FatigueTestCreateView(CreateView):
    model = FatigueTest
    form_class = FatigueTestForm
    template_name = 'materials/fatigue_test_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(MaterialBatch, pk=kwargs['batch_pk'])
        if not self.batch.can_add_fatigue_test():
            messages.error(request, '该批次处于断裂/审核/归档状态，无法新增疲劳测试记录')
            return redirect('materials:batch_detail', pk=self.batch.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.batch
        existing = self.batch.fatigue_tests.filter(is_flagged=False)
        if existing.exists():
            cycles = list(existing.values_list('cycle_count', flat=True))
            loads = list(existing.values_list('load_force', flat=True))
            context['reference_stats'] = {
                'avg_cycles': round(sum(cycles) / len(cycles), 0),
                'min_cycles': min(cycles),
                'max_cycles': max(cycles),
                'avg_load': round(sum(loads) / len(loads), 2),
                'min_load': min(loads),
                'max_load': max(loads),
                'test_count': existing.count(),
            }
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.batch
        return kwargs

    def form_valid(self, form):
        form.instance.batch = self.batch
        response = super().form_valid(form)
        self._check_and_create_anomaly(form.instance)
        return response

    def _check_and_create_anomaly(self, test):
        detector = AnomalyDetector(test.batch)
        anomalies = detector.check_fatigue_test(test, exclude_pk=test.pk)
        if anomalies:
            detector.create_anomaly_logs(
                anomalies, DataAnomalyLog.SOURCE_FATIGUE, test.pk
            )

    def get_success_url(self):
        messages.success(self.request, '疲劳测试记录添加成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.batch.pk})


class FatigueTestUpdateView(UpdateView):
    model = FatigueTest
    form_class = FatigueTestForm
    template_name = 'materials/fatigue_test_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.object.batch
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        detector = AnomalyDetector(self.object.batch)
        anomalies = detector.check_fatigue_test(self.object, exclude_pk=self.object.pk)
        if anomalies:
            detector.create_anomaly_logs(
                anomalies, DataAnomalyLog.SOURCE_FATIGUE, self.object.pk
            )
        return response

    def get_success_url(self):
        messages.success(self.request, '疲劳测试记录更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class FatigueTestDeleteView(DeleteView):
    model = FatigueTest
    template_name = 'materials/fatigue_test_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '疲劳测试记录已删除')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class ProcessParamCreateView(CreateView):
    model = MaterialProcessParam
    form_class = MaterialProcessParamForm
    template_name = 'materials/param_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.batch = get_object_or_404(MaterialBatch, pk=kwargs['batch_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.batch
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.batch
        return kwargs

    def form_valid(self, form):
        form.instance.batch = self.batch
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, '工艺参数添加成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.batch.pk})


class ProcessParamUpdateView(UpdateView):
    model = MaterialProcessParam
    form_class = MaterialProcessParamForm
    template_name = 'materials/param_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['batch'] = self.object.batch
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['batch'] = self.object.batch
        return kwargs

    def get_success_url(self):
        messages.success(self.request, '工艺参数更新成功')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class ProcessParamDeleteView(DeleteView):
    model = MaterialProcessParam
    template_name = 'materials/param_confirm_delete.html'

    def get_success_url(self):
        messages.success(self.request, '工艺参数已删除')
        return reverse('materials:batch_detail', kwargs={'pk': self.object.batch.pk})


class BatchCompareView(View):
    def get(self, request):
        batch_ids = request.GET.getlist('batches')
        batches = MaterialBatch.objects.filter(id__in=batch_ids) if batch_ids else []
        all_batches = MaterialBatch.objects.all()

        chart_datasets = []
        stress_strain_datasets = []
        colors = [
            '#2563eb', '#dc2626', '#16a34a', '#ca8a04',
            '#9333ea', '#0891b2', '#ea580c', '#4f46e5'
        ]
        for idx, batch in enumerate(batches):
            tests = batch.tension_tests.order_by('test_time')
            data = []
            ss_data = []
            for test in tests:
                data.append({
                    'x': float(test.elongation),
                    'y': float(test.tension_force),
                })
                if test.stress is not None and test.strain is not None:
                    ss_data.append({
                        'x': float(test.strain),
                        'y': float(test.stress),
                    })
            chart_datasets.append({
                'label': f'{batch.batch_number} - {batch.material_source}',
                'data': data,
                'color': colors[idx % len(colors)],
            })
            if ss_data:
                stress_strain_datasets.append({
                    'label': f'{batch.batch_number} - {batch.material_source}',
                    'data': ss_data,
                    'color': colors[idx % len(colors)],
                })

        comparison_table = []
        analyzer = StatisticsAnalyzer()
        for batch in batches:
            stats = analyzer.get_batch_comprehensive_stats(batch)
            comparison_table.append({
                'batch_number': batch.batch_number,
                'pk': batch.pk,
                'source': batch.material_source,
                'diameter': batch.diameter,
                'initial_length': batch.initial_length,
                'status': batch.get_status_display(),
                'is_broken': batch.is_broken,
                'tension_test_count': batch.test_count,
                'fatigue_test_count': batch.fatigue_test_count,
                'max_force': batch.max_tension_force,
                'max_elongation': batch.max_elongation,
                'avg_rebound': batch.avg_rebound_rate,
                'youngs_modulus': batch.youngs_modulus,
                'tensile_strength': batch.tensile_strength,
                'elongation_at_break': batch.elongation_at_break,
                'fatigue_cycles_to_failure': batch.fatigue_cycles_to_failure,
                'fatigue_endurance_limit': batch.fatigue_endurance_limit,
                'anomaly_count': batch.anomaly_count,
            })

        context = {
            'all_batches': all_batches,
            'selected_batches': batches,
            'selected_ids': [str(b.id) for b in batches],
            'chart_datasets_json': json.dumps(chart_datasets, ensure_ascii=False),
            'stress_strain_datasets_json': json.dumps(stress_strain_datasets, ensure_ascii=False),
            'comparison_table_json': json.dumps(comparison_table, ensure_ascii=False),
        }
        return render(request, 'materials/batch_compare.html', context)


class StatisticsView(View):
    def get(self, request):
        analyzer = StatisticsAnalyzer()
        global_stats = analyzer.get_global_statistics()

        batches = MaterialBatch.objects.all()
        tension_tests = TensionTest.objects.all()
        fatigue_tests = FatigueTest.objects.all()

        stats = {
            'total_batches': batches.count(),
            'total_tension_tests': tension_tests.count(),
            'total_fatigue_tests': fatigue_tests.count(),
            'broken_count': sum(1 for b in batches if b.is_broken),
            'abnormal_break_count': tension_tests.filter(abnormal_break=True).count(),
            'flagged_tension_count': tension_tests.filter(is_flagged=True).count(),
            'flagged_fatigue_count': fatigue_tests.filter(is_flagged=True).count(),
        }

        force_values = list(tension_tests.values_list('tension_force', flat=True))
        elongation_values = list(tension_tests.values_list('elongation', flat=True))
        rebound_values = list(
            tension_tests.filter(rebound_rate__isnull=False).values_list('rebound_rate', flat=True)
        )

        tension_stats = {}
        if force_values:
            tension_stats['force'] = analyzer.basic_stats(force_values)
        if elongation_values:
            tension_stats['elongation'] = analyzer.basic_stats(elongation_values)
        if rebound_values:
            tension_stats['rebound'] = analyzer.basic_stats(rebound_values)

        fatigue_stats = {}
        cycle_values = list(fatigue_tests.values_list('cycle_count', flat=True))
        load_values = list(fatigue_tests.values_list('load_force', flat=True))
        if cycle_values:
            fatigue_stats['cycles'] = analyzer.basic_stats(cycle_values)
        if load_values:
            fatigue_stats['load'] = analyzer.basic_stats(load_values)
        result_dist = {}
        for choice_val, choice_label in FatigueTest.RESULT_CHOICES:
            result_dist[choice_val] = {
                'label': choice_label,
                'count': fatigue_tests.filter(result=choice_val).count()
            }
        fatigue_stats['result_distribution'] = result_dist

        batch_comparison_data = []
        for batch in batches:
            batch_stats = analyzer.get_batch_comprehensive_stats(batch)
            row = {
                'label': batch.batch_number,
                'pk': batch.pk,
                'source': batch.material_source,
                'diameter': batch.diameter,
                'initial_length': batch.initial_length,
                'test_count': batch.test_count,
                'is_broken': batch.is_broken,
                'max_force': batch.max_tension_force or 0,
                'avg_force': (batch_stats.get('tension', {}) or {}).get('force', {}).get('mean', 0) if batch_stats.get('tension') else 0,
                'max_elongation': batch.max_elongation or 0,
                'avg_rebound': batch.avg_rebound_rate or 0,
                'youngs_modulus': batch.youngs_modulus,
                'tensile_strength': batch.tensile_strength,
                'elongation_at_break': batch.elongation_at_break,
            }
            batch_comparison_data.append(row)

        try:
            SnapshotGenerator.generate_daily()
        except Exception:
            pass

        snapshots = StatisticalSnapshot.objects.filter(
            snapshot_type=StatisticalSnapshot.SNAPSHOT_TYPE_DAILY
        ).order_by('-snapshot_date')[:30]
        snapshot_data = []
        for s in snapshots:
            snapshot_data.append({
                'date': s.snapshot_date.isoformat(),
                'total_batches': s.total_batches,
                'active_batches': s.active_batches,
                'broken_batches': s.broken_batches,
                'tension_tests': s.total_tension_tests,
                'fatigue_tests': s.total_fatigue_tests,
                'avg_force': s.avg_force or 0,
                'avg_rebound': s.avg_rebound_rate or 0,
                'anomalies': s.anomaly_count,
            })
        snapshot_data.reverse()

        context = {
            'stats': stats,
            'tension_stats': tension_stats,
            'fatigue_stats': fatigue_stats,
            'batch_comparison_data_json': json.dumps(batch_comparison_data, ensure_ascii=False),
            'global_stats': global_stats,
            'trend_data_json': json.dumps(global_stats.get('trend', []), ensure_ascii=False),
            'snapshot_data_json': json.dumps(snapshot_data, ensure_ascii=False),
            'source_distribution_json': json.dumps(
                global_stats.get('source_distribution', []), ensure_ascii=False
            ),
        }
        return render(request, 'materials/statistics.html', context)


class AnomalyListView(ListView):
    model = DataAnomalyLog
    template_name = 'materials/anomaly_list.html'
    context_object_name = 'anomalies'
    paginate_by = 20

    def get_queryset(self):
        queryset = DataAnomalyLog.objects.all()
        resolved = self.request.GET.get('resolved')
        if resolved == '0':
            queryset = queryset.filter(is_resolved=False)
        elif resolved == '1':
            queryset = queryset.filter(is_resolved=True)
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        source = self.request.GET.get('source')
        if source:
            queryset = queryset.filter(source_type=source)
        return queryset.select_related('batch')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['resolved_filter'] = self.request.GET.get('resolved', '')
        context['severity_filter'] = self.request.GET.get('severity', '')
        context['source_filter'] = self.request.GET.get('source', '')
        context['severity_choices'] = DataAnomalyLog.SEVERITY_CHOICES
        context['source_choices'] = DataAnomalyLog.SOURCE_CHOICES
        total = DataAnomalyLog.objects.count()
        resolved = DataAnomalyLog.objects.filter(is_resolved=True).count()
        context['anomaly_summary'] = {
            'total': total,
            'resolved': resolved,
            'unresolved': total - resolved,
            'high': DataAnomalyLog.objects.filter(
                severity=DataAnomalyLog.SEVERITY_HIGH, is_resolved=False
            ).count(),
            'medium': DataAnomalyLog.objects.filter(
                severity=DataAnomalyLog.SEVERITY_MEDIUM, is_resolved=False
            ).count(),
            'low': DataAnomalyLog.objects.filter(
                severity=DataAnomalyLog.SEVERITY_LOW, is_resolved=False
            ).count(),
        }
        return context


class AnomalyResolveView(View):
    def get(self, request, pk):
        anomaly = get_object_or_404(DataAnomalyLog, pk=pk)
        if anomaly.is_resolved:
            messages.info(request, '该异常已处理')
            return redirect('materials:anomaly_list')
        form = AnomalyResolveForm(instance=anomaly)
        context = {
            'anomaly': anomaly,
            'form': form,
        }
        return render(request, 'materials/anomaly_resolve.html', context)

    def post(self, request, pk):
        anomaly = get_object_or_404(DataAnomalyLog, pk=pk)
        form = AnomalyResolveForm(request.POST, instance=anomaly)
        if form.is_valid():
            anomaly = form.save(commit=False)
            anomaly.is_resolved = True
            anomaly.resolved_at = timezone.now()
            anomaly.save()
            messages.success(request, '异常数据已处理')
            return redirect('materials:anomaly_list')
        context = {
            'anomaly': anomaly,
            'form': form,
        }
        return render(request, 'materials/anomaly_resolve.html', context)


class BatchStatsAPIView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        analyzer = StatisticsAnalyzer()
        stats = analyzer.get_batch_comprehensive_stats(batch)
        return JsonResponse(stats, safe=False, json_dumps_params={'ensure_ascii': False})


class GlobalStatsAPIView(View):
    def get(self, request):
        analyzer = StatisticsAnalyzer()
        stats = analyzer.get_global_statistics()
        return JsonResponse(stats, safe=False, json_dumps_params={'ensure_ascii': False})


class CalculateReboundAPIView(View):
    def get(self, request):
        try:
            initial_length = float(request.GET.get('initial_length', 0))
            length_before = float(request.GET.get('length_before', 0))
            length_after = float(request.GET.get('length_after', 0))
        except (TypeError, ValueError):
            return HttpResponseBadRequest('参数必须为数字')

        errors = ReboundRateCalculator.validate_inputs(
            initial_length, length_before, length_after
        )
        if errors:
            return JsonResponse({'success': False, 'errors': errors})

        result = ReboundRateCalculator.calculate(
            initial_length, length_before, length_after
        )
        return JsonResponse({
            'success': True,
            'rebound_rate': result,
        })


class LifePredictionDashboardView(View):
    def get(self, request):
        batches = MaterialBatch.objects.all()
        total_batches = batches.count()

        predictions = LifePrediction.objects.filter(is_latest=True)
        pred_count = predictions.count()

        if predictions.exists():
            avg_life = round(
                sum(p.life_score for p in predictions) / pred_count, 1
            )
            avg_durability = round(
                sum(p.durability_score for p in predictions) / pred_count, 1
            )
            avg_stability = round(
                sum(p.stability_score for p in predictions) / pred_count, 1
            )
            avg_risk = round(
                sum(p.risk_score for p in predictions) / pred_count, 1
            )
        else:
            avg_life = avg_durability = avg_stability = avg_risk = 0

        risk_dist = {}
        for val, label in LifePrediction.RISK_LEVEL_CHOICES:
            risk_dist[val] = {
                'label': label,
                'count': predictions.filter(risk_level=val).count(),
            }

        high_risk = predictions.filter(
            risk_level__in=[LifePrediction.RISK_LEVEL_HIGH, LifePrediction.RISK_LEVEL_CRITICAL]
        ).select_related('batch').order_by('-risk_score')[:10]

        ranker = BatchRanker()
        try:
            top_overall = ranker.get_rankings(BatchRanking.RANKING_TYPE_OVERALL, limit=5)
        except Exception:
            top_overall = []

        recent_predictions = predictions.select_related('batch').order_by('-predicted_at')[:10]

        bow_types = BowType.objects.all()

        context = {
            'total_batches': total_batches,
            'pred_count': pred_count,
            'avg_life': avg_life,
            'avg_durability': avg_durability,
            'avg_stability': avg_stability,
            'avg_risk': avg_risk,
            'risk_dist_json': json.dumps(risk_dist, ensure_ascii=False),
            'high_risk_list': high_risk,
            'top_overall': top_overall,
            'recent_predictions': recent_predictions,
            'bow_types': bow_types,
            'all_batches': batches,
            'ranking_types': BatchRanking.RANKING_TYPE_CHOICES,
        }
        return render(request, 'materials/life_prediction_dashboard.html', context)


class RunLifePredictionView(View):
    def post(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        try:
            predictor = LifePredictor(batch)
            result = predictor.predict()
            pred = result['prediction']
            messages.success(request, f'寿命预测完成，综合评分{pred.life_score}分，风险等级：{pred.get_risk_level_display()}')
        except Exception as e:
            messages.error(request, f'预测失败：{str(e)}')
            return redirect('materials:batch_detail', pk=pk)
        return redirect('materials:life_prediction_detail', pk=pred.pk)


class RunAllLifePredictionsView(View):
    def post(self, request):
        batches = MaterialBatch.objects.all()
        success_count = 0
        fail_count = 0
        for batch in batches:
            try:
                predictor = LifePredictor(batch)
                predictor.predict()
                success_count += 1
            except Exception:
                fail_count += 1
        try:
            ranker = BatchRanker()
            ranker.generate_rankings()
        except Exception:
            pass
        messages.success(request, f'批量预测完成：成功{success_count}个，失败{fail_count}个')
        return redirect('materials:life_prediction_dashboard')


class LifePredictionDetailView(View):
    def get(self, request, pk):
        prediction = get_object_or_404(LifePrediction.objects.select_related('batch'), pk=pk)
        batch = prediction.batch

        history = LifePrediction.objects.filter(
            batch=batch
        ).order_by('-predicted_at')[:20]

        history_chart = []
        for p in history:
            history_chart.append({
                'x': p.predicted_at.strftime('%Y-%m-%d %H:%M'),
                'life_score': float(p.life_score),
                'durability': float(p.durability_score),
                'stability': float(p.stability_score),
                'risk_score': float(p.risk_score),
            })
        history_chart.reverse()

        radar_data = {
            'labels': ['耐久性', '稳定性', '抗拉强度', '疲劳寿命', '回弹性能', '安全裕度'],
            'values': [
                float(prediction.durability_score),
                float(prediction.stability_score),
                min((batch.tensile_strength or 0) / 10, 100),
                min((batch.fatigue_cycles_to_failure or 0) / 100, 100),
                (batch.avg_rebound_rate or 0),
                100 - float(prediction.risk_score),
            ],
        }

        try:
            matcher = BowTypeMatcher(batch)
            bow_matchings = matcher.match_all_bow_types()[:5]
        except Exception:
            bow_matchings = BowTypeMatching.objects.filter(
                batch=batch
            ).select_related('bow_type').order_by('-match_score')[:5]

        try:
            recommender = MaterialRecommender(batch)
            rec_results = recommender.generate_recommendations(top_n=5)
            recommendations = [r['recommendation'] for r in rec_results]
        except Exception:
            recommendations = MaterialRecommendation.objects.filter(
                source_batch=batch
            ).select_related('recommended_batch').order_by('-overall_score')[:5]

        bow_chart_data = []
        for m in bow_matchings:
            bow_chart_data.append({
                'name': m.bow_type.name,
                'category': m.bow_type.get_category_display(),
                'score': float(m.match_score),
                'level': m.get_match_level_display(),
            })

        factor_breakdown = []
        factor_labels = ['寿命评分', '耐久性', '稳定性', '风险惩罚']
        factor_values = [
            float(prediction.life_score),
            float(prediction.durability_score),
            float(prediction.stability_score),
            float(prediction.risk_score),
        ]
        factor_colors = ['#2563eb', '#16a34a', '#9333ea', '#dc2626']
        for label, val, color in zip(factor_labels, factor_values, factor_colors):
            factor_breakdown.append({
                'label': label,
                'value': val,
                'color': color,
            })

        context = {
            'prediction': prediction,
            'batch': batch,
            'history': history,
            'history_chart_json': json.dumps(history_chart, ensure_ascii=False),
            'radar_data_json': json.dumps(radar_data, ensure_ascii=False),
            'bow_matchings': bow_matchings,
            'recommendations': recommendations,
            'bow_chart_json': json.dumps(bow_chart_data, ensure_ascii=False),
            'factor_breakdown_json': json.dumps(factor_breakdown, ensure_ascii=False),
        }
        return render(request, 'materials/life_prediction_detail.html', context)


class BatchRecommendationsView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        try:
            recommender = MaterialRecommender(batch)
            results = recommender.generate_recommendations(top_n=10)
        except Exception as e:
            messages.error(request, f'推荐生成失败：{str(e)}')
            results = []

        rec_list = []
        chart_data = []
        for r in results:
            rec = r['recommendation']
            gains = r['gains']
            rec_list.append({
                'recommendation': rec,
                'gains': gains,
                'target_prediction': r['target_prediction'],
            })
            chart_data.append({
                'name': rec.recommended_batch.batch_number,
                'similarity': float(rec.similarity_score),
                'performance': float(max(-50, min(rec.performance_score, 50)) + 50),
                'overall': float(rec.overall_score),
            })

        context = {
            'source_batch': batch,
            'recommendations': rec_list,
            'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
        }
        return render(request, 'materials/material_recommendations.html', context)


class BatchBowMatchingView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        try:
            matcher = BowTypeMatcher(batch)
            matchings = matcher.match_all_bow_types()
        except Exception as e:
            messages.error(request, f'匹配计算失败：{str(e)}')
            matchings = BowTypeMatching.objects.filter(
                batch=batch
            ).select_related('bow_type').order_by('-match_score')

        detail_data = []
        for m in matchings:
            criteria = m.criteria_results or {}
            criteria_list = []
            for k, v in criteria.items():
                label_map = {
                    'diameter': '直径匹配',
                    'tensile_strength': '抗拉强度',
                    'fatigue_cycles': '疲劳循环',
                    'life_score': '寿命评分',
                    'safety_factor': '安全系数',
                }
                criteria_list.append({
                    'key': label_map.get(k, k),
                    'result': v.get('result', ''),
                    'score': v.get('score', 0),
                    'message': v.get('message', ''),
                })
            detail_data.append({
                'matching': m,
                'criteria': criteria_list,
            })

        chart_data = []
        for m in matchings:
            chart_data.append({
                'name': m.bow_type.name,
                'category': m.bow_type.get_category_display(),
                'score': float(m.match_score),
                'level': m.match_level,
            })

        context = {
            'batch': batch,
            'matchings_detail': detail_data,
            'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
        }
        return render(request, 'materials/bow_matching.html', context)


class BatchRankingView(View):
    def get(self, request):
        ranking_type = request.GET.get('type', BatchRanking.RANKING_TYPE_OVERALL)
        ranker = BatchRanker()

        try:
            if request.GET.get('refresh') == '1':
                ranker.generate_rankings()
                messages.success(request, '排行榜已更新')
        except Exception as e:
            messages.warning(request, f'排行榜更新异常：{str(e)}')

        rankings_by_type = {}
        for rt_val, rt_label in BatchRanking.RANKING_TYPE_CHOICES:
            rankings_by_type[rt_val] = ranker.get_rankings(rt_val, limit=20)

        current_rankings = rankings_by_type.get(ranking_type, [])

        chart_data = []
        for r in current_rankings:
            chart_data.append({
                'rank': r.rank,
                'name': r.batch.batch_number,
                'score': float(r.score),
                'source': r.batch.material_source,
                'pk': r.batch.pk,
            })

        compare_chart = {}
        for rt_val, rt_label in BatchRanking.RANKING_TYPE_CHOICES:
            rs = rankings_by_type[rt_val][:5]
            compare_chart[rt_val] = {
                'label': rt_label,
                'data': [
                    {'name': r.batch.batch_number, 'score': float(r.score)}
                    for r in rs
                ]
            }

        context = {
            'ranking_type': ranking_type,
            'ranking_types': BatchRanking.RANKING_TYPE_CHOICES,
            'current_rankings': current_rankings,
            'rankings_by_type': rankings_by_type,
            'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
            'compare_chart_json': json.dumps(compare_chart, ensure_ascii=False),
        }
        return render(request, 'materials/batch_ranking.html', context)


class RunBatchRankingsView(View):
    def post(self, request):
        try:
            ranker = BatchRanker()
            ranker.generate_rankings()
            messages.success(request, '全部排行榜更新成功')
        except Exception as e:
            messages.error(request, f'排行榜生成失败：{str(e)}')
        return redirect('materials:batch_ranking')


class ApiLifePredictionView(View):
    def post(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        try:
            predictor = LifePredictor(batch)
            result = predictor.predict()
            pred = result['prediction']
            return JsonResponse({
                'success': True,
                'data': {
                    'id': pred.pk,
                    'life_score': pred.life_score,
                    'durability_score': pred.durability_score,
                    'stability_score': pred.stability_score,
                    'risk_level': pred.risk_level,
                    'risk_level_display': pred.get_risk_level_display(),
                    'risk_score': pred.risk_score,
                    'predicted_cycles': pred.predicted_cycles_to_failure,
                    'predicted_hours': pred.predicted_lifetime_hours,
                    'key_factors': pred.key_factors,
                    'warning_signs': pred.warning_signs,
                    'recommendations': pred.recommendations,
                },
                'details': {
                    'durability': result.get('durability_details', {}),
                    'stability': result.get('stability_details', {}),
                    'anomaly': result.get('anomaly_details', {}),
                },
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiBatchRecommendationsView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        try:
            top_n = int(request.GET.get('top', 5))
            recommender = MaterialRecommender(batch)
            results = recommender.generate_recommendations(top_n=top_n)
            data = []
            for r in results:
                rec = r['recommendation']
                tp = r['target_prediction']
                data.append({
                    'id': rec.pk,
                    'recommended_batch': {
                        'id': rec.recommended_batch.pk,
                        'batch_number': rec.recommended_batch.batch_number,
                        'source': rec.recommended_batch.material_source,
                        'diameter': rec.recommended_batch.diameter,
                        'status': rec.recommended_batch.get_status_display(),
                    },
                    'similarity_score': rec.similarity_score,
                    'performance_score': rec.performance_score,
                    'overall_score': rec.overall_score,
                    'similarity_factors': rec.similarity_factors,
                    'advantages': rec.advantages,
                    'caveats': rec.caveats,
                    'gains': r['gains'],
                    'target_life_score': tp.life_score,
                    'target_risk_level': tp.get_risk_level_display(),
                })
            return JsonResponse({
                'success': True,
                'source_batch': {
                    'id': batch.pk,
                    'batch_number': batch.batch_number,
                },
                'recommendations': data,
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiBowMatchingView(View):
    def get(self, request, pk):
        batch = get_object_or_404(MaterialBatch, pk=pk)
        try:
            matcher = BowTypeMatcher(batch)
            matchings = matcher.match_all_bow_types()
            data = []
            for m in matchings:
                data.append({
                    'id': m.pk,
                    'bow_type': {
                        'id': m.bow_type.pk,
                        'name': m.bow_type.name,
                        'category': m.bow_type.get_category_display(),
                    },
                    'match_level': m.match_level,
                    'match_level_display': m.get_match_level_display(),
                    'match_score': m.match_score,
                    'criteria_results': m.criteria_results,
                    'notes': m.notes,
                })
            return JsonResponse({
                'success': True,
                'batch': {
                    'id': batch.pk,
                    'batch_number': batch.batch_number,
                },
                'matchings': data,
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiBatchRankingView(View):
    def get(self, request):
        try:
            ranking_type = request.GET.get('type', BatchRanking.RANKING_TYPE_OVERALL)
            limit = int(request.GET.get('limit', 20))
            ranker = BatchRanker()
            rankings = ranker.get_rankings(ranking_type, limit=limit)
            data = []
            for r in rankings:
                pred = LifePrediction.objects.filter(batch=r.batch, is_latest=True).first()
                item = {
                    'rank': r.rank,
                    'score': r.score,
                    'batch': {
                        'id': r.batch.pk,
                        'batch_number': r.batch.batch_number,
                        'source': r.batch.material_source,
                        'diameter': r.batch.diameter,
                        'status': r.batch.get_status_display(),
                    },
                }
                if pred:
                    item['life_score'] = pred.life_score
                    item['risk_level'] = pred.get_risk_level_display()
                data.append(item)
            return JsonResponse({
                'success': True,
                'ranking_type': ranking_type,
                'ranking_type_display': dict(BatchRanking.RANKING_TYPE_CHOICES).get(ranking_type, ''),
                'rankings': data,
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiPredictionVisualizationView(View):
    def get(self, request, pk):
        prediction = get_object_or_404(LifePrediction.objects.select_related('batch'), pk=pk)
        batch = prediction.batch

        history = LifePrediction.objects.filter(batch=batch).order_by('predicted_at')
        trend_data = []
        for p in history:
            trend_data.append({
                'time': p.predicted_at.strftime('%Y-%m-%d %H:%M'),
                'life_score': float(p.life_score),
                'durability': float(p.durability_score),
                'stability': float(p.stability_score),
                'risk_score': float(p.risk_score),
            })

        radar_data = {
            'labels': ['耐久性', '稳定性', '抗拉强度', '疲劳寿命', '回弹性能', '安全裕度'],
            'values': [
                float(prediction.durability_score),
                float(prediction.stability_score),
                min((batch.tensile_strength or 0) / 10, 100),
                min((batch.fatigue_cycles_to_failure or 0) / 100, 100),
                (batch.avg_rebound_rate or 0),
                max(0, 100 - float(prediction.risk_score)),
            ],
        }

        gauge_data = {
            'life_score': {
                'value': float(prediction.life_score),
                'label': '寿命评分',
                'thresholds': [30, 50, 70, 100],
            },
            'risk_score': {
                'value': float(prediction.risk_score),
                'label': '风险指数',
                'thresholds': [25, 50, 75, 100],
            },
        }

        batch_tests = batch.tension_tests.filter(is_flagged=False).order_by('test_time')
        fatigue_tests = batch.fatigue_tests.filter(is_flagged=False).order_by('test_time')

        tension_trend = []
        for t in batch_tests:
            tension_trend.append({
                'time': t.test_time.strftime('%Y-%m-%d %H:%M'),
                'force': float(t.tension_force),
                'elongation': float(t.elongation),
                'rebound': float(t.rebound_rate) if t.rebound_rate else None,
                'broken': t.is_broken,
            })

        fatigue_sncurve = []
        for ft in fatigue_tests:
            fatigue_sncurve.append({
                'cycles': ft.cycle_count,
                'load': float(ft.load_force),
                'result': ft.result,
                'result_display': ft.get_result_display(),
            })

        return JsonResponse({
            'success': True,
            'batch': {
                'id': batch.pk,
                'batch_number': batch.batch_number,
            },
            'prediction': {
                'life_score': prediction.life_score,
                'durability_score': prediction.durability_score,
                'stability_score': prediction.stability_score,
                'risk_level': prediction.get_risk_level_display(),
                'risk_score': prediction.risk_score,
                'predicted_cycles': prediction.predicted_cycles_to_failure,
                'predicted_hours': prediction.predicted_lifetime_hours,
                'key_factors': prediction.key_factors,
                'warning_signs': prediction.warning_signs,
                'recommendations': prediction.recommendations,
            },
            'trend_data': trend_data,
            'radar_data': radar_data,
            'gauge_data': gauge_data,
            'tension_trend': tension_trend,
            'fatigue_sncurve': fatigue_sncurve,
        }, json_dumps_params={'ensure_ascii': False})


class RecipeListView(ListView):
    model = ProcessRecipe
    template_name = 'materials/recipe_list.html'
    context_object_name = 'recipes'
    paginate_by = 20

    def get_queryset(self):
        queryset = ProcessRecipe.objects.all().select_related('target_bow_type')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                recipe_code__icontains=q
            ) | queryset.filter(
                recipe_name__icontains=q
            ) | queryset.filter(
                base_material__icontains=q
            )
        recipe_type = self.request.GET.get('type')
        if recipe_type:
            queryset = queryset.filter(recipe_type=recipe_type)
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['type_filter'] = self.request.GET.get('type', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['recipe_type_choices'] = ProcessRecipe.RECIPE_TYPE_CHOICES
        context['status_choices'] = ProcessRecipe.STATUS_CHOICES
        total = ProcessRecipe.objects.count()
        context['recipe_summary'] = {
            'total': total,
            'draft': ProcessRecipe.objects.filter(status=ProcessRecipe.STATUS_DRAFT).count(),
            'validated': ProcessRecipe.objects.filter(status=ProcessRecipe.STATUS_VALIDATED).count(),
            'approved': ProcessRecipe.objects.filter(status=ProcessRecipe.STATUS_APPROVED).count(),
            'traditional': ProcessRecipe.objects.filter(recipe_type=ProcessRecipe.RECIPE_TYPE_TRADITIONAL).count(),
            'modern': ProcessRecipe.objects.filter(recipe_type=ProcessRecipe.RECIPE_TYPE_MODERN).count(),
        }
        return context


class RecipeDetailView(DetailView):
    model = ProcessRecipe
    template_name = 'materials/recipe_detail.html'
    context_object_name = 'recipe'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recipe = self.object
        context['params'] = recipe.params.all()
        context['performance_targets'] = recipe.performance_targets.all()
        context['predictions'] = recipe.predictions.all()[:10]
        context['trials'] = recipe.trials.all().select_related('material_batch', 'target_bow_type')[:10]
        context['suggestions'] = recipe.suggestions.all()[:20]
        context['derived_recipes'] = recipe.derived_recipes.all()[:5]

        latest_pred = recipe.latest_prediction
        if latest_pred:
            radar_data = {
                'labels': ['耐久性', '稳定性', '回弹表现', '强度'],
                'values': [
                    float(latest_pred.predicted_durability),
                    float(latest_pred.predicted_stability),
                    float(latest_pred.predicted_rebound),
                    float(latest_pred.predicted_strength or 0),
                ],
            }
            context['radar_data_json'] = json.dumps(radar_data, ensure_ascii=False)

            history = recipe.predictions.all().order_by('predicted_at')[:20]
            history_chart = []
            for p in history:
                history_chart.append({
                    'time': p.predicted_at.strftime('%Y-%m-%d %H:%M'),
                    'overall': float(p.predicted_overall),
                    'durability': float(p.predicted_durability),
                    'stability': float(p.predicted_stability),
                    'rebound': float(p.predicted_rebound),
                    'risk_score': float(p.predicted_risk_score),
                })
            context['history_chart_json'] = json.dumps(history_chart, ensure_ascii=False)
        return context


class RecipeCreateView(CreateView):
    model = ProcessRecipe
    fields = [
        'recipe_code', 'recipe_name', 'recipe_type', 'status',
        'target_bow_type', 'description', 'base_material',
        'twist_direction', 'twist_count', 'strand_count',
        'coating_material', 'curing_method', 'curing_temperature',
        'curing_duration', 'pretreatment_process', 'weaving_method',
        'created_by', 'parent_recipe', 'version'
    ]
    template_name = 'materials/recipe_form.html'

    def get_success_url(self):
        return reverse('materials:recipe_detail', kwargs={'pk': self.object.pk})


class RecipeUpdateView(UpdateView):
    model = ProcessRecipe
    fields = [
        'recipe_code', 'recipe_name', 'recipe_type', 'status',
        'target_bow_type', 'description', 'base_material',
        'twist_direction', 'twist_count', 'strand_count',
        'coating_material', 'curing_method', 'curing_temperature',
        'curing_duration', 'pretreatment_process', 'weaving_method',
        'created_by', 'approved_by', 'parent_recipe', 'version'
    ]
    template_name = 'materials/recipe_form.html'

    def get_success_url(self):
        return reverse('materials:recipe_detail', kwargs={'pk': self.object.pk})


class RecipeDeleteView(DeleteView):
    model = ProcessRecipe
    template_name = 'materials/recipe_confirm_delete.html'

    def get_success_url(self):
        return reverse('materials:recipe_list')


class RunRecipePredictionView(View):
    def post(self, request, pk):
        recipe = get_object_or_404(ProcessRecipe, pk=pk)
        try:
            predictor = RecipePredictor(recipe)
            result = predictor.predict()
            pred = result['prediction']
            messages.success(
                request,
                f'配方性能预测完成，综合评分{pred.predicted_overall}分，风险等级：{pred.get_predicted_risk_level_display()}'
            )
        except Exception as e:
            messages.error(request, f'预测失败：{str(e)}')
        return redirect('materials:recipe_detail', pk=pk)


class RecipeSuggestionsView(View):
    def get(self, request, pk):
        recipe = get_object_or_404(ProcessRecipe, pk=pk)
        try:
            generator = OptimizationGenerator(recipe)
            suggestions = generator.generate_from_prediction()
            messages.success(request, f'已生成{len(suggestions)}条优化建议')
        except Exception as e:
            messages.error(request, f'生成建议失败：{str(e)}')
        return redirect('materials:recipe_detail', pk=pk)


class TrialPlanListView(ListView):
    model = TrialPlan
    template_name = 'materials/trial_list.html'
    context_object_name = 'trials'
    paginate_by = 20

    def get_queryset(self):
        queryset = TrialPlan.objects.all().select_related('recipe', 'material_batch', 'target_bow_type')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                plan_code__icontains=q
            ) | queryset.filter(
                plan_name__icontains=q
            ) | queryset.filter(
                recipe__recipe_code__icontains=q
            )
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        trial_type = self.request.GET.get('type')
        if trial_type:
            queryset = queryset.filter(trial_type=trial_type)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['type_filter'] = self.request.GET.get('type', '')
        context['status_choices'] = TrialPlan.PLAN_STATUS_CHOICES
        context['trial_type_choices'] = TrialPlan.TRIAL_TYPE_CHOICES
        total = TrialPlan.objects.count()
        context['trial_summary'] = {
            'total': total,
            'planning': TrialPlan.objects.filter(status=TrialPlan.PLAN_STATUS_PLANNING).count(),
            'in_progress': TrialPlan.objects.filter(status=TrialPlan.PLAN_STATUS_IN_PROGRESS).count(),
            'completed': TrialPlan.objects.filter(status=TrialPlan.PLAN_STATUS_COMPLETED).count(),
            'failed': TrialPlan.objects.filter(status=TrialPlan.PLAN_STATUS_FAILED).count(),
        }
        return context


class TrialPlanDetailView(DetailView):
    model = TrialPlan
    template_name = 'materials/trial_detail.html'
    context_object_name = 'trial'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trial = self.object
        context['recipe'] = trial.recipe
        context['results'] = trial.results.all()

        perf_chart = []
        for r in trial.results.all():
            perf_chart.append({
                'sample': r.sample_id,
                'durability': float(r.durability_score or 0),
                'stability': float(r.stability_score or 0),
                'rebound': float(r.rebound_performance or 0),
                'strength': float(r.strength_score or 0),
                'overall': float(r.overall_score or 0),
                'risk': float(r.risk_score or 0),
            })
        context['perf_chart_json'] = json.dumps(perf_chart, ensure_ascii=False)

        result_dist = {}
        for val, label in TrialResult.RESULT_CHOICES:
            result_dist[val] = {
                'label': label,
                'count': trial.results.filter(result_status=val).count()
            }
        context['result_dist_json'] = json.dumps(result_dist, ensure_ascii=False)
        return context


class TrialPlanCreateView(CreateView):
    model = TrialPlan
    fields = [
        'plan_code', 'plan_name', 'recipe', 'material_batch',
        'trial_type', 'status', 'target_bow_type', 'sample_count',
        'planned_start_date', 'planned_end_date', 'tester',
        'test_environment', 'preparation_notes', 'test_procedure',
        'expected_outcomes', 'created_by'
    ]
    template_name = 'materials/trial_form.html'

    def get_success_url(self):
        return reverse('materials:trial_detail', kwargs={'pk': self.object.pk})


class TrialPlanUpdateView(UpdateView):
    model = TrialPlan
    fields = [
        'plan_code', 'plan_name', 'recipe', 'material_batch',
        'trial_type', 'status', 'target_bow_type', 'sample_count',
        'planned_start_date', 'planned_end_date', 'actual_start_date',
        'actual_end_date', 'tester', 'test_environment',
        'preparation_notes', 'test_procedure', 'expected_outcomes'
    ]
    template_name = 'materials/trial_form.html'

    def get_success_url(self):
        return reverse('materials:trial_detail', kwargs={'pk': self.object.pk})


class TrialPlanStartView(View):
    def post(self, request, pk):
        trial = get_object_or_404(TrialPlan, pk=pk)
        try:
            trial.start()
            messages.success(request, f'试制方案"{trial.plan_name}"已启动')
        except Exception as e:
            messages.error(request, f'启动失败：{str(e)}')
        return redirect('materials:trial_detail', pk=pk)


class TrialPlanCompleteView(View):
    def post(self, request, pk):
        trial = get_object_or_404(TrialPlan, pk=pk)
        try:
            trial.complete()
            analyzer = TrialAnalyzer(trial)
            analysis = analyzer.analyze_results()
            for r in trial.results.all():
                if r.trial_plan.recipe_id:
                    generator = OptimizationGenerator(r.trial_plan.recipe, r)
                    generator.generate_from_trial_result()
            messages.success(request, f'试制方案"{trial.plan_name}"已完成，已生成分析结果和优化建议')
        except Exception as e:
            messages.error(request, f'完成失败：{str(e)}')
        return redirect('materials:trial_detail', pk=pk)


class TrialResultCreateView(CreateView):
    model = TrialResult
    fields = [
        'sample_id', 'test_date', 'test_operator',
        'durability_score', 'stability_score', 'rebound_performance',
        'strength_score', 'risk_level', 'measured_force',
        'measured_elongation', 'measured_rebound_rate', 'fatigue_cycles',
        'measured_diameter', 'weight_per_meter', 'lifespan_estimate_hours',
        'estimated_shots', 'is_broken', 'break_location', 'break_mode',
        'break_reason', 'observations', 'issues_found', 'recommendations',
        'raw_data_reference', 'notes'
    ]
    template_name = 'materials/trial_result_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.trial_plan = get_object_or_404(TrialPlan, pk=kwargs.get('pk'))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.trial_plan = self.trial_plan
        result = super().form_valid(form)
        self.object.evaluate_targets()
        self.object.save()
        return result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['trial_plan'] = self.trial_plan
        context['recipe'] = self.trial_plan.recipe
        return context

    def get_success_url(self):
        return reverse('materials:trial_detail', kwargs={'pk': self.trial_plan.pk})


class TrialResultUpdateView(UpdateView):
    model = TrialResult
    fields = [
        'sample_id', 'test_date', 'test_operator',
        'durability_score', 'stability_score', 'rebound_performance',
        'strength_score', 'risk_level', 'measured_force',
        'measured_elongation', 'measured_rebound_rate', 'fatigue_cycles',
        'measured_diameter', 'weight_per_meter', 'lifespan_estimate_hours',
        'estimated_shots', 'is_broken', 'break_location', 'break_mode',
        'break_reason', 'observations', 'issues_found', 'recommendations',
        'raw_data_reference', 'notes'
    ]
    template_name = 'materials/trial_result_form.html'

    def form_valid(self, form):
        result = super().form_valid(form)
        self.object.evaluate_targets()
        self.object.save()
        return result

    def get_success_url(self):
        return reverse('materials:trial_detail', kwargs={'pk': self.object.trial_plan_id})


class EvaluateTrialResultView(View):
    def post(self, request, pk):
        result = get_object_or_404(TrialResult, pk=pk)
        try:
            met, missed = result.evaluate_targets()
            result.save()
            messages.success(request, f'目标评估完成：达成{len(met)}项，未达成{len(missed)}项')
        except Exception as e:
            messages.error(request, f'评估失败：{str(e)}')
        return redirect('materials:trial_detail', pk=result.trial_plan_id)


class TrialAnalysisView(View):
    def get(self, request, pk):
        trial = get_object_or_404(TrialPlan, pk=pk)
        try:
            analyzer = TrialAnalyzer(trial)
            analysis = analyzer.analyze_results()
            context = {
                'trial': trial,
                'analysis': analysis,
                'analysis_json': json.dumps(analysis, ensure_ascii=False),
            }
            return render(request, 'materials/trial_analysis.html', context)
        except Exception as e:
            messages.error(request, f'分析失败：{str(e)}')
            return redirect('materials:trial_detail', pk=pk)


class RecipeCompareView(View):
    def get(self, request):
        recipe_ids = request.GET.getlist('ids')
        comparison_data = None
        recipes = ProcessRecipe.objects.all()[:20]
        selected_recipes = []

        if recipe_ids:
            selected_recipes = ProcessRecipe.objects.filter(pk__in=recipe_ids)
            if selected_recipes.count() >= 2:
                comparator = RecipeComparator(selected_recipes)
                comparison_data = comparator.full_comparison()

        context = {
            'recipes': recipes,
            'selected_recipes': selected_recipes,
            'selected_ids': recipe_ids,
            'comparison': comparison_data,
            'comparison_json': json.dumps(comparison_data, ensure_ascii=False) if comparison_data else None,
        }
        return render(request, 'materials/recipe_compare.html', context)


class ApiRecipePredictionView(View):
    def post(self, request, pk):
        recipe = get_object_or_404(ProcessRecipe, pk=pk)
        try:
            predictor = RecipePredictor(recipe)
            result = predictor.predict()
            pred = result['prediction']
            return JsonResponse({
                'success': True,
                'data': {
                    'id': pred.pk,
                    'durability': pred.predicted_durability,
                    'stability': pred.predicted_stability,
                    'rebound': pred.predicted_rebound,
                    'strength': pred.predicted_strength,
                    'overall': pred.predicted_overall,
                    'risk_level': pred.predicted_risk_level,
                    'risk_level_display': pred.get_predicted_risk_level_display(),
                    'risk_score': pred.predicted_risk_score,
                    'lifespan_hours': pred.predicted_lifespan_hours,
                    'confidence': pred.confidence_level,
                    'key_factors': pred.key_factors,
                    'strengths': pred.strength_analysis,
                    'weaknesses': pred.weakness_analysis,
                    'optimization_suggestions': pred.optimization_suggestions,
                },
                'component_scores': result.get('component_scores', {}),
                'reference_data': result.get('reference_data'),
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiRecipeCompareView(View):
    def get(self, request):
        try:
            ids_str = request.GET.get('ids', '')
            ids = [int(x) for x in ids_str.split(',') if x.strip()]
            compare_type = request.GET.get('type', 'full')

            if len(ids) < 2:
                return JsonResponse({
                    'success': False,
                    'error': '至少需要选择2个配方进行对比'
                }, status=400)

            recipes = ProcessRecipe.objects.filter(pk__in=ids)
            if recipes.count() < 2:
                return JsonResponse({
                    'success': False,
                    'error': '找到的配方数量不足'
                }, status=404)

            comparator = RecipeComparator(recipes)
            if compare_type == 'performance':
                data = comparator.compare_performance()
            elif compare_type == 'params':
                data = comparator.compare_parameters()
            else:
                data = comparator.full_comparison()

            return JsonResponse({
                'success': True,
                'compare_type': compare_type,
                'data': data,
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiTrialAnalysisView(View):
    def get(self, request, pk):
        trial = get_object_or_404(TrialPlan, pk=pk)
        try:
            analyzer = TrialAnalyzer(trial)
            analysis = analyzer.analyze_results()
            return JsonResponse({
                'success': True,
                'trial': {
                    'id': trial.pk,
                    'code': trial.plan_code,
                    'name': trial.plan_name,
                },
                'analysis': analysis,
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiRecipeSuggestionsView(View):
    def get(self, request, pk):
        recipe = get_object_or_404(ProcessRecipe, pk=pk)
        try:
            status_filter = request.GET.get('status', '')
            severity_filter = request.GET.get('severity', '')

            qs = recipe.suggestions.all()
            if status_filter:
                qs = qs.filter(status=status_filter)
            if severity_filter:
                qs = qs.filter(severity=severity_filter)

            data = []
            for s in qs:
                data.append({
                    'id': s.pk,
                    'title': s.title,
                    'category': s.category,
                    'category_display': s.get_category_display(),
                    'severity': s.severity,
                    'severity_display': s.get_severity_display(),
                    'status': s.status,
                    'status_display': s.get_status_display(),
                    'description': s.description,
                    'current_state': s.current_state,
                    'suggested_action': s.suggested_action,
                    'expected_improvement': s.expected_improvement,
                    'affected_params': s.affected_params,
                    'generated_by': s.generated_by,
                    'created_at': s.created_at.strftime('%Y-%m-%d %H:%M'),
                })
            return JsonResponse({
                'success': True,
                'recipe': {
                    'id': recipe.pk,
                    'code': recipe.recipe_code,
                    'name': recipe.recipe_name,
                },
                'total': qs.count(),
                'suggestions': data,
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def post(self, request, pk):
        recipe = get_object_or_404(ProcessRecipe, pk=pk)
        try:
            trial_result_id = request.POST.get('trial_result_id')
            trial_result = None
            if trial_result_id:
                trial_result = TrialResult.objects.filter(pk=trial_result_id, trial_plan__recipe=recipe).first()

            generator = OptimizationGenerator(recipe, trial_result)
            if trial_result:
                suggestions = generator.generate_all()
            else:
                suggestions = generator.generate_from_prediction()

            data = [{'id': s.pk, 'title': s.title, 'severity': s.get_severity_display()} for s in suggestions]
            return JsonResponse({
                'success': True,
                'generated_count': len(suggestions),
                'suggestions': data,
            }, json_dumps_params={'ensure_ascii': False})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiRecipeVisualizationView(View):
    def get(self, request, pk):
        recipe = get_object_or_404(ProcessRecipe, pk=pk)

        latest_pred = recipe.latest_prediction
        radar_data = None
        gauge_data = None
        history_data = []
        trial_performance = []

        if latest_pred:
            radar_data = {
                'labels': ['耐久性', '稳定性', '回弹表现', '强度'],
                'values': [
                    float(latest_pred.predicted_durability),
                    float(latest_pred.predicted_stability),
                    float(latest_pred.predicted_rebound),
                    float(latest_pred.predicted_strength or 0),
                ],
            }
            gauge_data = {
                'overall': {
                    'value': float(latest_pred.predicted_overall),
                    'label': '综合评分',
                    'thresholds': [30, 50, 70, 100],
                },
                'risk': {
                    'value': float(latest_pred.predicted_risk_score),
                    'label': '风险指数',
                    'thresholds': [25, 50, 75, 100],
                },
            }

        history = recipe.predictions.all().order_by('predicted_at')[:30]
        for p in history:
            history_data.append({
                'time': p.predicted_at.strftime('%Y-%m-%d %H:%M'),
                'overall': float(p.predicted_overall),
                'durability': float(p.predicted_durability),
                'stability': float(p.predicted_stability),
                'rebound': float(p.predicted_rebound),
                'risk_score': float(p.predicted_risk_score),
            })

        for trial in recipe.trials.all().prefetch_related('results'):
            for r in trial.results.all():
                trial_performance.append({
                    'trial_code': trial.plan_code,
                    'sample': r.sample_id,
                    'date': r.test_date.isoformat(),
                    'durability': float(r.durability_score or 0),
                    'stability': float(r.stability_score or 0),
                    'rebound': float(r.rebound_performance or 0),
                    'strength': float(r.strength_score or 0),
                    'overall': float(r.overall_score or 0),
                    'risk_level': r.risk_level,
                    'result_status': r.result_status,
                })

        return JsonResponse({
            'success': True,
            'recipe': {
                'id': recipe.pk,
                'code': recipe.recipe_code,
                'name': recipe.recipe_name,
                'type': recipe.get_recipe_type_display(),
                'status': recipe.get_status_display(),
            },
            'radar_data': radar_data,
            'gauge_data': gauge_data,
            'prediction_history': history_data,
            'trial_performance': trial_performance,
        }, json_dumps_params={'ensure_ascii': False})
