from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Magnolia
from .forms import MagnoliaForm


def magnolia_list(request):
    magnolias = Magnolia.objects.all()
    return render(request, 'magnolias/magnolia_list.html', {'magnolias': magnolias})


def magnolia_detail(request, pk):
    magnolia = get_object_or_404(Magnolia, pk=pk)
    return render(request, 'magnolias/magnolia_detail.html', {'magnolia': magnolia})


def magnolia_create(request):
    if request.method == 'POST':
        form = MagnoliaForm(request.POST, request.FILES)
        if form.is_valid():
            magnolia = form.save()
            messages.success(request, 'Magnolia logged successfully!')
            return redirect(magnolia.get_absolute_url())
    else:
        form = MagnoliaForm()
    return render(request, 'magnolias/magnolia_form.html', {'form': form, 'title': 'Log a Magnolia'})


def magnolia_update(request, pk):
    magnolia = get_object_or_404(Magnolia, pk=pk)
    if request.method == 'POST':
        form = MagnoliaForm(request.POST, request.FILES, instance=magnolia)
        if form.is_valid():
            form.save()
            messages.success(request, 'Magnolia updated successfully!')
            return redirect(magnolia.get_absolute_url())
    else:
        form = MagnoliaForm(instance=magnolia)
    return render(request, 'magnolias/magnolia_form.html', {'form': form, 'title': 'Edit Magnolia', 'magnolia': magnolia})


def magnolia_delete(request, pk):
    magnolia = get_object_or_404(Magnolia, pk=pk)
    if request.method == 'POST':
        magnolia.delete()
        messages.success(request, 'Magnolia entry deleted.')
        return redirect('magnolias:list')
    return render(request, 'magnolias/magnolia_confirm_delete.html', {'magnolia': magnolia})
