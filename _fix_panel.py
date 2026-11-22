path = 'src/views/panel.py'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    s = f.read()

old = '''            # Fill type + gradient stop controls
            state.setdefault("fill_type_rects", {})
            state.setdefault("fill_stop_rects", {})
            state.setdefault("fill_stop_add_rect", pygame.Rect(0, 0, 0, 0))
            state.setdefault("fill_stop_remove_rect", pygame.Rect(0, 0, 0, 0))
            state.setdefault("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
            if color_target == "fill":
                fill_mode = "none"  # (kept for structure) - replaced block below in code
  (no-op marker not needed)
I see I already replaced the whole block above; this is redundant. Let us not duplicate. I'll skip. Actually better to ensure I didn't leave broken state. The replacement I made above already includes the logic, so no need to edit again. I'll continue.
                if fill_grad is not None:
                    fill_mode = str(fill_grad.get("type", "linear"))
                elif stroke is not None and stroke.get("fill_color") is not None:
                    fill_mode = "solid"
                labels = [("solid", "Solid"), ("linear", "Linear"), ("radial", "Radial")]
                bw = (PANEL_W - 40 - 8) // 3
                for i, (key, label) in enumerate(labels):
                    r = pygame.Rect(x + i * (bw + 4), y, bw, 24)
                    state["fill_type_rects"][key] = r
                    active = (fill_mode == key)
                    bg = TOOL_ACTIVE if active else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
                    pygame.draw.rect(screen, bg, r, border_radius=5)
                    pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, r, 1, border_radius=5)
                    t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
                    screen.blit(t, t.get_rect(center=r.center))
                y += 30
                state["fill_stop_rects"] = {}
                if fill_grad is not None:
                    sw = 26
                    for i in range(2):
                        r = pygame.Rect(x + i * (sw + 8), y, sw, sw)
                        state["fill_stop_rects"][str(i)] = r
                        cstop = get_gradient_stop_color(fill_grad, i) if 'get_gradient_stop_color' in globals() else (0,0,0,1)
                        draw_swatch(screen, r, cstop, i == fill_grad_stop, mouse_pos)
                    lbl = font_small.render(f"Stop {fill_grad_stop + 1}", True, TEXT_COLOR)
                    screen.blit(lbl, (x + 2 * (sw + 8) + 4, y + 5))
                    y += sw + 8
            else:
                state["fill_type_rects"] = {}
                state["fill_stop_rects"] = {}'''

new = r'''            # Fill type + gradient stop controls
            state.setdefault("fill_type_rects", {})
            state.setdefault("fill_stop_rects", {})
            state.setdefault("fill_stop_add_rect", pygame.Rect(0, 0, 0, 0))
            state.setdefault("fill_stop_remove_rect", pygame.Rect(0, 0, 0, 0))
            state.setdefault("fill_stop_pos_rect", pygame.Rect(0, 0, 0, 0))
            if color_target == "fill":
                fill_mode = "none"
                if fill_grad is not None:
                    fill_mode = str(fill_grad.get("type", "linear"))
                elif stroke is not None and stroke.get("fill_color") is not None:
                    fill_mode = "solid"
                labels = [("solid", "Solid"), ("linear", "Linear"), ("radial", "Radial")]
                bw = (PANEL_W - 40 - 8) // 3
                for i, (key, label) in enumerate(labels):
                    r = pygame.Rect(x + i * (bw + 4), y, bw, 24)
                    state["fill_type_rects"][key] = r
                    active = (fill_mode == key)
                    bg = TOOL_ACTIVE if active else (BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG)
                    pygame.draw.rect(screen, bg, r, border_radius=5)
                    pygame.draw.rect(screen, ACCENT if active else BUTTON_BORDER, r, 1, border_radius=5)
                    t = font_small.render(label, True, ACCENT if active else TEXT_COLOR)
                    screen.blit(t, t.get_rect(center=r.center))
                y += 30

                # gradient stops (multi-stop)
                state["fill_stop_rects"] = {}
                state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)
                if fill_grad is not None:
                    _get_stops = globals().get("get_gradient_stops")
                    if callable(_get_stops):
                        try:
                            stops = _get_stops(fill_grad) or []
                        except Exception:
                            stops = list(fill_grad.get("stops") or [])
                    else:
                        stops = list(fill_grad.get("stops") or [])
                    if not stops:
                        stops = [{"pos": 0.0, "color": [0.0, 0.0, 0.0, 1.0]},
                                 {"pos": 1.0, "color": [1.0, 1.0, 1.0, 1.0]}]
                    nstops = len(stops)
                    try:
                        fill_grad_stop = int(state.get("fill_gradient_stop", 0) or 0)
                    except Exception:
                        fill_grad_stop = 0
                    fill_grad_stop = max(0, min(fill_grad_stop, nstops - 1))
                    state["fill_gradient_stop"] = fill_grad_stop

                    avail_w = PANEL_W - 40
                    btn_w = 22
                    gap = 6
                    sw_area_w = max(60, avail_w - 2 * (btn_w + gap))
                    sw = max(18, min(26, (sw_area_w - max(0, nstops - 1) * 4) // max(1, nstops)))
                    sw_gap = 4 if nstops > 7 else 6
                    for i in range(nstops):
                        r = pygame.Rect(x + i * (sw + sw_gap), y, sw, sw)
                        if r.right > x + sw_area_w:
                            r.x = x + sw_area_w - sw
                        state["fill_stop_rects"][str(i)] = r
                        st = stops[i]
                        if isinstance(st, dict):
                            cstop = color_rgba(st.get("color"), (0, 0, 0, 1))
                        else:
                            try:
                                cstop = color_rgba(st[1], (0, 0, 0, 1))
                            except Exception:
                                cstop = (0.0, 0.0, 0.0, 1.0)
                        draw_swatch(screen, r, cstop, i == fill_grad_stop, mouse_pos)
                    bx = x + sw_area_w + gap
                    add_r = pygame.Rect(bx, y, btn_w, sw)
                    rem_r = pygame.Rect(bx + btn_w + 4, y, btn_w, sw)
                    state["fill_stop_add_rect"] = add_r
                    state["fill_stop_remove_rect"] = rem_r
                    for r, label, enabled_btn in ((add_r, "+", True), (rem_r, "-", nstops > 2)):
                        if enabled_btn:
                            bg = BUTTON_HOVER if r.collidepoint(mouse_pos) else BUTTON_BG
                            border = BUTTON_BORDER
                            col = TEXT_COLOR
                        else:
                            bg = (235, 238, 242)
                            border = (220, 224, 230)
                            col = MUTED_COLOR
                        pygame.draw.rect(screen, bg, r, border_radius=5)
                        pygame.draw.rect(screen, border, r, 1, border_radius=5)
                        t = font_small.render(label, True, col)
                        screen.blit(t, t.get_rect(center=r.center))
                    y += sw + 6

                    # selected stop position (distance)
                    sel_st = stops[fill_grad_stop] if 0 <= fill_grad_stop < nstops else stops[0]
                    try:
                        sel_pos = float((sel_st or {}).get("pos", 0.0)) if isinstance(sel_st, dict) else float(sel_st[0])
                    except Exception:
                        sel_pos = 0.0
                    sel_pos = clamp(sel_pos, 0.0, 1.0)
                    pos_label = font_small.render(f"Stop {fill_grad_stop + 1}  Pos {int(round(sel_pos * 100))}%", True, TEXT_COLOR)
                    screen.blit(pos_label, (x, y))
                    y += 16
                    pos_h = 10
                    pos_rect = pygame.Rect(x, y, PANEL_W - 40, pos_h)
                    state["fill_stop_pos_rect"] = pos_rect
                    for ix in range(pos_rect.w):
                        tt = ix / max(1, pos_rect.w - 1)
                        samp = (128, 128, 128)
                        try:
                            ordered = []
                            for s in stops:
                                if isinstance(s, dict):
                                    ordered.append((float(s.get("pos", 0.0)), color_rgba(s.get("color"), (0, 0, 0, 1))))
                                else:
                                    try:
                                        ordered.append((float(s[0]), color_rgba(s[1], (0, 0, 0, 1))))
                                    except Exception:
                                        pass
                            ordered.sort(key=lambda t: t[0])
                            if ordered:
                                if tt <= ordered[0][0]:
                                    sc = ordered[0][1]
                                elif tt >= ordered[-1][0]:
                                    sc = ordered[-1][1]
                                else:
                                    sc = ordered[-1][1]
                                    for a, b in zip(ordered, ordered[1:]):
                                        pa, ca = a; pb, cb = b
                                        if pa <= tt <= pb:
                                            lt = 0.0 if pb - pa <= 1e-9 else (tt - pa) / (pb - pa)
                                            sc = tuple(ca[k] + (cb[k] - ca[k]) * lt for k in range(4))
                                            break
                                bgv = 235 if (ix // 6) % 2 == 0 else 210
                                a = float(sc[3]) if len(sc) >= 4 else 1.0
                                samp = (int((sc[0] * a + (bgv / 255.0) * (1 - a)) * 255),
                                        int((sc[1] * a + (bgv / 255.0) * (1 - a)) * 255),
                                        int((sc[2] * a + (bgv / 255.0) * (1 - a)) * 255))
                        except Exception:
                            pass
                        pygame.draw.line(screen, samp, (pos_rect.x + ix, pos_rect.y), (pos_rect.x + ix, pos_rect.bottom - 1))
                    pygame.draw.rect(screen, BUTTON_BORDER, pos_rect, 1, border_radius=4)
                    px = pos_rect.x + int(sel_pos * (pos_rect.w - 1))
                    pygame.draw.rect(screen, (255, 255, 255), (px - 3, pos_rect.y - 2, 6, pos_rect.h + 4), 2, border_radius=2)
                    pygame.draw.rect(screen, (0, 0, 0), (px - 3, pos_rect.y - 2, 6, pos_rect.h + 4), 1, border_radius=2)
                    y += pos_h + 8
            else:
                state["fill_type_rects"] = {}
                state["fill_stop_rects"] = {}
                state["fill_stop_add_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_remove_rect"] = pygame.Rect(0, 0, 0, 0)
                state["fill_stop_pos_rect"] = pygame.Rect(0, 0, 0, 0)'''

if old not in s:
    print('NOT FOUND')
    raise SystemExit(1)
s = s.replace(old, new)
with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(s)
print('fixed')
