from django import template

register = template.Library()

@register.filter
def duration_format(value):
    """
    Format seconds to Dd HH:MM or HH:MM format.
    """
    if value is None:
        return "00:00"
    
    try:
        total_seconds = int(value)
        days = total_seconds // 86400
        remaining_seconds = total_seconds % 86400
        hours = remaining_seconds // 3600
        minutes = (remaining_seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}"
        else:
            return f"{hours:02d}:{minutes:02d}"
    except (ValueError, TypeError):
        return "00:00"
@register.filter
def get_project_printers(project):
    """
    Returns a list of distinct printer names for a project.
    """
    printers = project.master_print_files.exclude(printer=None).values('printer__id', 'printer__name', 'printer__tag').distinct()
    unique = {}
    for p in printers:
        key = p['printer__id']
        if key not in unique:
            unique[key] = {'id': p['printer__id'], 'name': p['printer__name'], 'tag': p['printer__tag']}
    return list(unique.values())
@register.filter
def sum_quantities(outputs):
    """
    Sums the quantities of a list of ProjectOutput objects.
    """
    if not outputs:
        return 0
    return sum(o.quantity for o in outputs)

@register.filter
def multiply(value, arg):
    """
    Multiplies the value by the argument.
    """
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0
@register.filter
def remaining_for_output(work_order, output):
    """
    Returns the remaining quantity for a specific output in a work order.
    """
    if not work_order or not output:
        return 0
    return work_order.get_remaining_for_output(output)
@register.filter
def printed_ready_to_stock_for_output(work_order, output):
    """
    Returns the quantity of a specific output that has been printed but not yet stocked.
    """
    if not work_order or not output:
        return 0
    return work_order.get_printed_ready_to_stock_for_output(output)

@register.filter
def contrast_color(hex_color):
    """
    Returns 'black' or 'white' based on the contrast of the input hex color.
    """
    if not hex_color or not hex_color.startswith('#') or len(hex_color) != 7:
        return 'white'
    
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        # YIQ brightness formula
        yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000
        return 'black' if yiq >= 128 else 'white'
    except Exception:
        return 'white'
