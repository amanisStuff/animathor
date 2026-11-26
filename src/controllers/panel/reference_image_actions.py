"""Reference-image controls in the draw panel."""
import pygame


def reference_image_click(rects, state, document, ui, event,
                          pick_reference_image_path, load_reference_image, clamp):
        if rects.get("ref_load_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            path = pick_reference_image_path()
            if path:
                ref = load_reference_image(path)
                if ref is not None:
                    document.reference_image = ref
                    document.reference_error = None
                else:
                    document.reference_error = "Could not load reference image (unsupported or corrupt file)."
            return True
        elif rects.get("ref_vis_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            if document.reference_image:
                document.reference_image["visible"] = not document.reference_image.get("visible", True)
            return True
        elif rects.get("ref_clear_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            document.reference_image = None
            document.reference_error = None
            return True
        elif document.reference_image and rects.get("ref_opacity_rect", pygame.Rect(0,0,0,0)).collidepoint(event.pos):
            # Drag field: the click starts the scrub without jumping the value.
            start_opacity = clamp(document.reference_image.get("opacity", 0.5), 0.0, 1.0)
            state["ref_opacity_drag_start"] = (event.pos[0], start_opacity)
            ui.ref_opacity_drag = True
            return True
        return False
