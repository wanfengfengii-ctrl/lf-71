from django.urls import path
from . import views

app_name = 'materials'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('batches/', views.MaterialBatchListView.as_view(), name='batch_list'),
    path('batches/<int:pk>/', views.MaterialBatchDetailView.as_view(), name='batch_detail'),
    path('batches/create/', views.MaterialBatchCreateView.as_view(), name='batch_create'),
    path('batches/<int:pk>/edit/', views.MaterialBatchUpdateView.as_view(), name='batch_edit'),
    path('batches/<int:pk>/delete/', views.MaterialBatchDeleteView.as_view(), name='batch_delete'),
    path('batches/<int:pk>/review/', views.BatchReviewView.as_view(), name='batch_review'),
    path('batches/<int:pk>/flow-note/', views.BatchFlowNoteView.as_view(), name='batch_flow_note'),
    path('batches/<int:batch_pk>/tests/add/', views.TensionTestCreateView.as_view(), name='test_create'),
    path('tests/<int:pk>/edit/', views.TensionTestUpdateView.as_view(), name='test_edit'),
    path('tests/<int:pk>/delete/', views.TensionTestDeleteView.as_view(), name='test_delete'),
    path('batches/<int:batch_pk>/fatigue/add/', views.FatigueTestCreateView.as_view(), name='fatigue_test_create'),
    path('fatigue/<int:pk>/edit/', views.FatigueTestUpdateView.as_view(), name='fatigue_test_edit'),
    path('fatigue/<int:pk>/delete/', views.FatigueTestDeleteView.as_view(), name='fatigue_test_delete'),
    path('batches/<int:batch_pk>/params/add/', views.ProcessParamCreateView.as_view(), name='param_create'),
    path('params/<int:pk>/edit/', views.ProcessParamUpdateView.as_view(), name='param_edit'),
    path('params/<int:pk>/delete/', views.ProcessParamDeleteView.as_view(), name='param_delete'),
    path('compare/', views.BatchCompareView.as_view(), name='batch_compare'),
    path('statistics/', views.StatisticsView.as_view(), name='statistics'),
    path('anomalies/', views.AnomalyListView.as_view(), name='anomaly_list'),
    path('anomalies/<int:pk>/resolve/', views.AnomalyResolveView.as_view(), name='anomaly_resolve'),
    path('api/batch-stats/<int:pk>/', views.BatchStatsAPIView.as_view(), name='api_batch_stats'),
    path('api/global-stats/', views.GlobalStatsAPIView.as_view(), name='api_global_stats'),
    path('api/calc-rebound/', views.CalculateReboundAPIView.as_view(), name='api_calc_rebound'),
]
