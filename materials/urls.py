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
    path('batches/<int:batch_pk>/tests/add/', views.TensionTestCreateView.as_view(), name='test_create'),
    path('tests/<int:pk>/edit/', views.TensionTestUpdateView.as_view(), name='test_edit'),
    path('tests/<int:pk>/delete/', views.TensionTestDeleteView.as_view(), name='test_delete'),
    path('compare/', views.BatchCompareView.as_view(), name='batch_compare'),
]
