from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from functools import wraps

def role_required(*allowed_roles):
    """
    Decorator to restrict access to users who belong to specific roles.
    If the user is not logged in or lacks the role, they are logged out
    and redirected to their respective login page.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Please log in to access this page.")
                if 'Staff' in allowed_roles:
                    return redirect('staff_login')
                elif 'Manager' in allowed_roles:
                    return redirect('manager_login')
                else:
                    return redirect('customer_login')
            
            # Check user role
            user_role = getattr(getattr(request.user, 'profile', None), 'role', None)
            
            # Superuser overrides everything for easy admin access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)
                
            # If authenticated but incorrect role, logout and display error
            logout(request)
            messages.error(request, f"Access denied. This section is restricted to {', '.join(allowed_roles)} accounts.")
            
            if 'Staff' in allowed_roles:
                return redirect('staff_login')
            elif 'Manager' in allowed_roles:
                return redirect('manager_login')
            else:
                return redirect('customer_login')
                
        return _wrapped_view
    return decorator
