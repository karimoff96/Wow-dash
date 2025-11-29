from django.shortcuts import render
from django.contrib.auth.decorators import login_required

def blankpage(request):
    context={
        "title": "Blank Page",
        "subTitle": "Blank Page",
    }
    return render(request,"blankpage.html", context)

    
def comingsoon(request):
    context={
        "title": "",
        "subTitle": "",
    }
    return render(request,"comingsoon.html", context)
    
def email(request):
    context={
        "title": "Email",
        "subTitle": "Components / Email",
    }
    return render(request,"email.html", context)
    
def faqs(request):
    context={
        "title": "Faq",
        "subTitle": "Faq",
    }
    return render(request,"faqs.html", context)
    
def gallery(request):
    context={
        "title": "Gallery",
        "subTitle": "Gallery",
    }
    return render(request,"gallery.html", context)

@login_required(login_url='admin_login')
def index(request):
    context={
        "title": "Dashboard",
        "subTitle": "AI",
    }
    return render(request,"index.html", context)
    
def kanban(request):
    context={
        "title": "Kanban",
        "subTitle": "Kanban",
    }
    return render(request,"kanban.html", context)
    
def maintenance(request):
    context={
        "title": "",
        "subTitle": "",
    }
    return render(request,"maintenance.html", context)
    
def notFound(request):
    context={
        "title": "404",
        "subTitle": "404",
    }
    return render(request,"notFound.html", context)
    
def pricing(request):
    context={
        "title": "Pricing",
        "subTitle": "Pricing",
    }
    return render(request,"pricing.html", context)
    
def stared(request):
    context={
        "title": "Email",
        "subTitle": "Components / Email",
    }
    return render(request,"stared.html", context)
    
def termsAndConditions(request):
    context={
        "title": "Terms & Condition",
        "subTitle": "Terms & Condition",
    }
    return render(request,"termsAndConditions.html", context)
    
def testimonials(request):
    context={
        "title": "Testimonials",
        "subTitle": "Testimonials",
    }
    return render(request,"testimonials.html", context)
    
def viewDetails(request):
    context={
        "title": "Email",
        "subTitle": "Components / Email",
    }
    return render(request,"viewDetails.html", context)
    
def widgets(request):
    context={
        "title": "Widgets",
        "subTitle": "Widgets",
    }
    return render(request,"widgets.html", context)
    