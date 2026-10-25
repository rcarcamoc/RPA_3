"""
Generadores de textos HTML y dashboards gráficos (Matplotlib) para los resúmenes de gestión RPA.
"""
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import MaxNLocator

from .summary_queries import (
    is_addendum,
    is_ya_ingresado,
    is_pending_approval,
    is_success_standard,
    is_success,
    is_error,
    is_in_progress,
)


def generar_texto_resumen_hourly(df_hora, df_dia, periodo_str):
    """Genera un mensaje de texto formateado en HTML, claro y amigable para usuarios no técnicos."""
    total_hora = len(df_hora) if df_hora is not None else 0
    total_dia = len(df_dia) if df_dia is not None else 0

    # Fecha amigable en español
    now = datetime.datetime.now()
    dias_es = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dia_nombre = dias_es[now.weekday()]
    fecha_fmt = f"{dia_nombre} {now.strftime('%d/%m')}"

    texto = "📊 <b>Resumen Horario RPA</b>\n"
    texto += f"🕒 <b>Ventana:</b> {periodo_str} hrs | <i>{fecha_fmt}</i>\n\n"

    # 1. Actividad en la última hora
    texto += "⚡ <b>Actividad en la última hora:</b>\n"
    if total_hora == 0:
        texto += "• ℹ️ <i>Sin nuevos casos en esta ventana (Robot en espera activa)</i>\n"
    else:
        conteo_hora = df_hora['estado'].value_counts()
        exitos_std_h = sum(cnt for st, cnt in conteo_hora.items() if is_success_standard(st))
        proceso_h = sum(cnt for st, cnt in conteo_hora.items() if is_in_progress(st))
        pendientes_h = sum(cnt for st, cnt in conteo_hora.items() if is_pending_approval(st))
        addendum_h = sum(cnt for st, cnt in conteo_hora.items() if is_addendum(st))
        ya_ingresado_h = sum(cnt for st, cnt in conteo_hora.items() if is_ya_ingresado(st))
        errores_h = sum(cnt for st, cnt in conteo_hora.items() if is_error(st))
        total_exitosos_h = exitos_std_h + pendientes_h + addendum_h + ya_ingresado_h

        if total_exitosos_h > 0:
            texto += f"• 🟢 <b>Exitosos:</b> <b>{total_exitosos_h}</b>\n"
            if exitos_std_h > 0:
                texto += f"   ├ ✅ Completados 100%: <b>{exitos_std_h}</b>\n"
            if pendientes_h > 0:
                texto += f"   ├ ⏳ Aprobación pendiente: <b>{pendientes_h}</b>\n"
            if addendum_h > 0:
                texto += f"   ├ 📝 Addendum: <b>{addendum_h}</b>\n"
            if ya_ingresado_h > 0:
                texto += f"   └ 🔁 Ya ingresado: <b>{ya_ingresado_h}</b>\n"
        if proceso_h > 0:
            texto += f"• ⏳ En ejecución: <b>{proceso_h}</b>\n"
        if errores_h > 0:
            texto += f"• ❌ Con incidencias: <b>{errores_h}</b>\n"

        # Otros estados no estándar
        for st, cnt in conteo_hora.items():
            if not (is_success(st) or is_in_progress(st) or is_error(st) or is_pending_approval(st)):
                texto += f"• ℹ️ {st}: <b>{cnt}</b>\n"

        texto += f"👉 <i>Total en la hora: {total_hora} casos gestionados</i>\n"

    texto += "\n📈 <b>Acumulado de la jornada (Hoy):</b>\n"
    if total_dia == 0:
        texto += "• 🎯 Total procesados hoy: <b>0 casos</b>\n"
        texto += "• 🟢 Alertas pendientes: <b>Ninguna</b> ✨\n"
    else:
        conteo_dia = df_dia['estado'].value_counts()
        exitos_std_d = sum(cnt for st, cnt in conteo_dia.items() if is_success_standard(st))
        pendientes_d = sum(cnt for st, cnt in conteo_dia.items() if is_pending_approval(st))
        addendum_d = sum(cnt for st, cnt in conteo_dia.items() if is_addendum(st))
        ya_ingresado_d = sum(cnt for st, cnt in conteo_dia.items() if is_ya_ingresado(st))
        errores_d = sum(cnt for st, cnt in conteo_dia.items() if is_error(st))
        completados_d = exitos_std_d + pendientes_d + addendum_d + ya_ingresado_d

        texto += f"• 🎯 Total procesados hoy: <b>{total_dia} casos</b>\n"
        if completados_d > 0:
            texto += f"• 🟢 <b>Exitosos (Total):</b> <b>{completados_d} casos</b>\n"
            if exitos_std_d > 0:
                texto += f"   ├ ✅ Completados 100%: <b>{exitos_std_d}</b>\n"
            if pendientes_d > 0:
                texto += f"   ├ ⏳ Aprobación pendiente: <b>{pendientes_d}</b> <i>(completados por RPA)</i>\n"
            if addendum_d > 0:
                texto += f"   ├ 📝 Addendum: <b>{addendum_d}</b> <i>(reclasificados)</i>\n"
            if ya_ingresado_d > 0:
                texto += f"   └ 🔁 Ya ingresado: <b>{ya_ingresado_d}</b> <i>(reclasificados)</i>\n"

        base_tasa = completados_d + errores_d
        tasa = (completados_d / base_tasa * 100) if base_tasa > 0 else 100.0
        tasa_emoji = "🟢" if tasa >= 95.0 else ("🟡" if tasa >= 80.0 else "🔴")
        texto += f"• {tasa_emoji} Tasa de efectividad: <b>{tasa:.1f}%</b> ({completados_d} de {base_tasa} gestionados)\n"

        # Desglose de errores y alertas
        sin_gestionar = 0
        if errores_d > 0 and 'estado_notificacion' in df_dia.columns:
            df_err = df_dia[df_dia['estado'].astype(str).str.lower().str.contains('error|fall', na=False) & ~df_dia['estado'].astype(str).str.lower().str.contains('aprobacion_pendiente|pending|addendum|ya ingresado|ya_ingresado', na=False)]
            sin_gestionar = len(df_err[df_err['estado_notificacion'] == 'Pendiente'])
            if sin_gestionar > 0:
                texto += f"• ❌ Errores técnicos: <b>{errores_d}</b> (🔴 <b>{sin_gestionar}</b> alerta{'s' if sin_gestionar > 1 else ''} sin gestionar en Telegram)\n"
            else:
                texto += f"• ❌ Errores técnicos: <b>{errores_d}</b> (🟢 Todas gestionadas)\n"
        elif errores_d == 0:
            texto += "• 🟢 Errores técnicos: <b>0</b> ✨\n"

    # Estado Operativo general
    texto += "\n"
    if total_dia == 0:
        texto += "💡 <b>Estado:</b> 🟢 <i>Sistema listo para operar</i>"
    elif 'sin_gestionar' in locals() and sin_gestionar > 0:
        texto += f"💡 <b>Estado:</b> ⚠️ <i>Atención requerida ({sin_gestionar} alerta{'s' if sin_gestionar > 1 else ''} sin gestionar en Telegram)</i>"
    elif total_hora > 0 and any(is_error(st) for st in df_hora['estado'].unique()):
        texto += "💡 <b>Estado:</b> ⚠️ <i>Incidencia en la última hora</i>"
    elif total_hora == 0:
        texto += "💡 <b>Estado:</b> 🟢 <i>Operación fluida (esperando nuevos casos)</i>"
    else:
        texto += "💡 <b>Estado:</b> 🟢 <i>Operación normal sin incidencias</i>"

    return texto


def generar_dashboard_ejecutivo(df_hora, df_dia, periodo_str, filename, is_daily=False):
    """Genera una imagen unificada estilo dashboard ejecutivo con KPIs superiores y gráfico de progresión."""
    fig = plt.figure(figsize=(10, 5.8), facecolor='#f8fafc', dpi=150)
    gs = gridspec.GridSpec(2, 4, height_ratios=[1.1, 2.3], hspace=0.32, wspace=0.25,
                           left=0.06, right=0.94, top=0.92, bottom=0.10)

    total_dia = len(df_dia) if df_dia is not None else 0

    exitos_d = sum(1 for e in df_dia['estado'] if is_success(e)) if total_dia > 0 else 0
    pendientes_d = sum(1 for e in df_dia['estado'] if is_pending_approval(e)) if total_dia > 0 else 0
    errores_d = sum(1 for e in df_dia['estado'] if is_error(e)) if total_dia > 0 else 0

    completados_d = exitos_d + pendientes_d
    base_tasa = completados_d + errores_d
    tasa_exito = (completados_d / base_tasa * 100) if base_tasa > 0 else 100.0

    # 4 Tarjetas KPI superiores
    subt_efectividad = f"{exitos_d} Compl. • {pendientes_d} Aprob. Pend." if pendientes_d > 0 else f"{completados_d} exitosos hoy"
    subt_exitosos = f"{exitos_d} 100% • {pendientes_d} Aprob. Pend." if pendientes_d > 0 else f"{completados_d} exitosos"

    if is_daily:
        kpis = [
            ('TOTAL DÍA', f'{total_dia}', 'Casos jornada', '#0f172a', '#ffffff', '#e2e8f0'),
            ('EXITOSOS', f'{completados_d}', subt_exitosos, '#15803d', '#f0fdf4', '#bbf7d0'),
            ('EFECTIVIDAD', f'{tasa_exito:.1f}%', subt_efectividad, '#0284c7' if tasa_exito >= 85 else '#b45309', '#f0f9ff' if tasa_exito >= 85 else '#fffbeb', '#bae6fd' if tasa_exito >= 85 else '#fde68a'),
            ('INCIDENCIAS', f'{errores_d}', 'Alertas jornada' if errores_d > 0 else 'Sin alertas activas', '#b91c1c' if errores_d > 0 else '#475569', '#fef2f2' if errores_d > 0 else '#ffffff', '#fecaca' if errores_d > 0 else '#e2e8f0')
        ]
    else:
        kpis = [
            ('TOTAL DÍA', f'{total_dia}', 'Casos acumulados', '#0f172a', '#ffffff', '#e2e8f0'),
            ('EXITOSOS HOY', f'{completados_d}', subt_exitosos, '#15803d', '#f0fdf4', '#bbf7d0'),
            ('EFECTIVIDAD', f'{tasa_exito:.1f}%', subt_efectividad, '#0284c7' if tasa_exito >= 85 else '#b45309', '#f0f9ff' if tasa_exito >= 85 else '#fffbeb', '#bae6fd' if tasa_exito >= 85 else '#fde68a'),
            ('INCIDENCIAS', f'{errores_d}', 'Alertas hoy' if errores_d > 0 else 'Sin alertas activas', '#b91c1c' if errores_d > 0 else '#475569', '#fef2f2' if errores_d > 0 else '#ffffff', '#fecaca' if errores_d > 0 else '#e2e8f0')
        ]

    for i, (title, val, subtitle, text_col, bg_col, border_col) in enumerate(kpis):
        ax_kpi = fig.add_subplot(gs[0, i])
        ax_kpi.axis('off')

        # Tarjeta redondeada moderna
        p_bbox = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                                boxstyle='round,pad=0.03,rounding_size=0.12',
                                ec=border_col, fc=bg_col, linewidth=1.2,
                                transform=ax_kpi.transAxes, zorder=1)
        ax_kpi.add_patch(p_bbox)

        ax_kpi.text(0.5, 0.77, title, ha='center', va='center', fontsize=9, fontweight='bold', color='#64748b', transform=ax_kpi.transAxes, zorder=2)
        ax_kpi.text(0.5, 0.44, val, ha='center', va='center', fontsize=19, fontweight='bold', color=text_col, transform=ax_kpi.transAxes, zorder=2)
        ax_kpi.text(0.5, 0.17, subtitle, ha='center', va='center', fontsize=8, color='#64748b', transform=ax_kpi.transAxes, zorder=2)

    # Gráfico inferior
    ax_chart = fig.add_subplot(gs[1, :])
    ax_chart.set_facecolor('#ffffff')

    # Fondo del chart card
    p_chart_bg = FancyBboxPatch((-0.03, -0.15), 1.06, 1.25,
                                boxstyle='round,pad=0.02,rounding_size=0.05',
                                ec='#e2e8f0', fc='#ffffff', linewidth=1.2,
                                transform=ax_chart.transAxes, zorder=0)
    ax_chart.add_patch(p_chart_bg)

    # Filtrar 'sin registros para trabajar' del gráfico
    df_chart = df_dia[df_dia['estado'] != 'sin registros para trabajar'].copy() if (df_dia is not None and not df_dia.empty) else pd.DataFrame()

    if not df_chart.empty:
        df_chart['hora'] = pd.to_datetime(df_chart['inicio']).dt.strftime('%H:00')
        agrupado = df_chart.groupby(['hora', 'estado']).size().unstack(fill_value=0)

        def get_col_color(c):
            cl = str(c).lower()
            if any(x in cl for x in ['pending', 'aprobacion_pendiente', 'pendiente']): return '#f59e0b'  # Ámbar
            if 'addendum' in cl: return '#3b82f6'  # Azul
            if any(x in cl for x in ['ya ingresado', 'ya_ingresado']): return '#8b5cf6'  # Púrpura
            if 'error' in cl or 'fall' in cl: return '#ef4444'  # Rojo coral
            if any(x in cl for x in ['terminado', 'finalizado', 'exito', 'éxito']): return '#10b981'  # Verde esmeralda
            if 'proceso' in cl: return '#0ea5e9'  # Azul cielo
            return '#94a3b8'  # Gris pizarra

        colors = [get_col_color(col) for col in agrupado.columns]

        def format_legend_label(col_name):
            cl = str(col_name).lower()
            if any(x in cl for x in ['pending', 'aprobacion_pendiente', 'pendiente']): return 'Aprobación Pendiente'
            if 'addendum' in cl: return 'Addendum'
            if any(x in cl for x in ['ya ingresado', 'ya_ingresado']): return 'Ya Ingresado'
            if any(x in cl for x in ['terminado', 'finalizado', 'éxito', 'exito']): return 'Completado 100%'
            if 'proceso' in cl: return 'En Proceso'
            if 'error' in cl or 'fall' in cl: return 'Error'
            return str(col_name)

        agrupado.columns = [format_legend_label(c) for c in agrupado.columns]

        agrupado.plot(kind='bar', stacked=True, color=colors, ax=ax_chart, width=0.45, edgecolor='#ffffff', linewidth=1, zorder=3)

        chart_title = f'Progresión Cierre Diario RPA ({periodo_str})' if is_daily else f'Progresión de Gestiones por Hora (Ventana {periodo_str})'
        ax_chart.set_title(chart_title, fontsize=11, fontweight='bold', color='#1e293b', pad=12, zorder=4)
        ax_chart.set_xlabel('', fontsize=9)
        ax_chart.set_ylabel('Casos', fontsize=9, color='#64748b', labelpad=8)
        ax_chart.tick_params(axis='x', rotation=0, colors='#334155', labelsize=9)
        ax_chart.tick_params(axis='y', colors='#64748b', labelsize=8)
        ax_chart.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax_chart.grid(axis='y', linestyle='--', alpha=0.35, color='#cbd5e1', zorder=1)

        for spine in ['top', 'right', 'left', 'bottom']:
            ax_chart.spines[spine].set_color('#e2e8f0')

        handles, labels = ax_chart.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        leg = ax_chart.legend(by_label.values(), by_label.keys(), frameon=True, facecolor='#ffffff', edgecolor='#e2e8f0', fontsize=8.5, loc='upper left')
        if leg:
            leg.set_zorder(5)

        for c in ax_chart.containers:
            ax_chart.bar_label(c, label_type='center', fontsize=8.5, color='#ffffff', fontweight='bold', fmt=lambda x: f'{int(x)}' if x > 0 else '', zorder=6)
    else:
        ax_chart.text(0.5, 0.5, 'ℹ️ Sin actividad registrada en esta jornada', ha='center', va='center', color='#94a3b8', fontsize=12, fontweight='bold', transform=ax_chart.transAxes)
        ax_chart.axis('off')

    plt.savefig(filename, dpi=150, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close(fig)
    return True


def generar_tabla_imagen(df_hora, df_dia, periodo_str, filename):
    """Función de compatibilidad: Redirige a generar_dashboard_ejecutivo."""
    return generar_dashboard_ejecutivo(df_hora, df_dia, periodo_str, filename)


def generar_grafico_barras(df, filename):
    """Función de compatibilidad: Redirige a generar_dashboard_ejecutivo."""
    df_vacio = pd.DataFrame(columns=['inicio', 'estado', 'estado_notificacion'])
    return generar_dashboard_ejecutivo(df_vacio, df, "Hoy", filename, is_daily=True)


def generar_texto_resumen_simple(df, tipo_reporte, periodo_str):
    """Genera un texto de resumen simple y estructurado (usado para el cierre diario)."""
    if df.empty:
        return f"📊 <b>Resumen {tipo_reporte} ({periodo_str})</b>\n\nℹ️ <i>No hubo gestiones registradas en este período.</i>"

    total = len(df)
    conteo_estados = df['estado'].value_counts()

    exitos_std = sum(cnt for st, cnt in conteo_estados.items() if is_success_standard(st))
    pendientes = sum(cnt for st, cnt in conteo_estados.items() if is_pending_approval(st))
    addendums = sum(cnt for st, cnt in conteo_estados.items() if is_addendum(st))
    ya_ingresados = sum(cnt for st, cnt in conteo_estados.items() if is_ya_ingresado(st))
    errores = sum(cnt for st, cnt in conteo_estados.items() if is_error(st))
    completados = exitos_std + pendientes + addendums + ya_ingresados
    base_tasa = completados + errores
    tasa = (completados / base_tasa * 100) if base_tasa > 0 else 100.0
    tasa_emoji = "🟢" if tasa >= 95.0 else ("🟡" if tasa >= 80.0 else "🔴")

    texto = f"📊 <b>Resumen {tipo_reporte}</b>\n"
    texto += f"📅 <i>{periodo_str}</i>\n\n"
    texto += f"🎯 <b>Total Gestionado:</b> <b>{total} casos</b>\n"
    texto += f"{tasa_emoji} <b>Tasa de Efectividad:</b> <b>{tasa:.1f}%</b> ({completados} de {base_tasa})\n\n"
    texto += "📋 <b>Desglose por Estado:</b>\n"

    if completados > 0:
        texto += f"• 🟢 <b>Exitosos (Total):</b> <b>{completados}</b>\n"
        if exitos_std > 0:
            texto += f"   ├ ✅ Completados 100%: <b>{exitos_std}</b>\n"
        if pendientes > 0:
            texto += f"   ├ ⏳ Aprobación Pendiente: <b>{pendientes}</b> <i>(completados por RPA)</i>\n"
        if addendums > 0:
            texto += f"   ├ 📝 Addendum: <b>{addendums}</b> <i>(reclasificados)</i>\n"
        if ya_ingresados > 0:
            texto += f"   └ 🔁 Ya Ingresado: <b>{ya_ingresados}</b> <i>(reclasificados)</i>\n"

    proceso = sum(cnt for st, cnt in conteo_estados.items() if is_in_progress(st))
    if proceso > 0:
        texto += f"• ⏳ En Proceso: <b>{proceso}</b>\n"

    if errores > 0:
        texto += f"• ❌ Con Incidencias / Error: <b>{errores}</b>\n"
        if 'estado_notificacion' in df.columns:
            df_err = df[df['estado'].astype(str).str.lower().str.contains('error|fall', na=False) & ~df['estado'].astype(str).str.lower().str.contains('aprobacion_pendiente|pending|addendum|ya ingresado|ya_ingresado', na=False)]
            sin_gestionar = len(df_err[df_err['estado_notificacion'] == 'Pendiente'])
            gestionados = len(df_err[df_err['estado_notificacion'] == 'Gestionado'])
            if sin_gestionar > 0:
                texto += f"   └ 🔴 <b>{sin_gestionar}</b> alerta{'s' if sin_gestionar > 1 else ''} sin gestionar en Telegram\n"
            if gestionados > 0:
                texto += f"   └ 🟢 <b>{gestionados}</b> gestionado{'s' if gestionados > 1 else ''}\n"

    for st, cnt in conteo_estados.items():
        if not (is_success(st) or is_in_progress(st) or is_error(st) or is_pending_approval(st)):
            texto += f"• ℹ️ {st}: <b>{cnt}</b>\n"

    return texto
