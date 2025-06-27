# -*- coding: utf-8 -*-
"""
Dashboard de Financiamiento de Facturas - Actualizado con nuevos estados, estructura de tasas, y limpieza de datos según estado financiero.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO
import os

st.set_page_config(layout="wide")
st.title("Dashboard de Financiamiento de Facturas")

# === RUTAS POR DEFECTO ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FACTURAS = os.path.join(BASE_DIR, "data", "facturas_ejemplo.xlsx")
DEFAULT_TASAS = os.path.join(BASE_DIR, "data", "estructura_tasas.xlsx")

# === SIDEBAR ===
with st.sidebar:
    st.header("Carga de datos")
    archivo = st.file_uploader("Archivo Excel de facturas", type=["xlsx"], key="facturas")
    archivo_tasas = st.file_uploader("Estructura de tasas", type=["xlsx"], key="tasas")

# Usar archivos por defecto si no se suben
if not archivo and os.path.exists(DEFAULT_FACTURAS):
    with open(DEFAULT_FACTURAS, "rb") as f:
        archivo = BytesIO(f.read())
        archivo.name = "facturas_ejemplo.xlsx"

if not archivo_tasas and os.path.exists(DEFAULT_TASAS):
    with open(DEFAULT_TASAS, "rb") as f:
        archivo_tasas = BytesIO(f.read())
        archivo_tasas.name = "estructura_tasas.xlsx"

# === MAIN ===
if archivo:
    df = pd.read_excel(archivo)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"Fecha Emisión": "Fecha_Emision"})
    df["Fecha_Emision"] = pd.to_datetime(df["Fecha_Emision"], dayfirst=True, errors='coerce')
    df["Fecha_Vencimiento"] = pd.to_datetime(df["Fecha_Vencimiento"], dayfirst=True, errors='coerce')

    # === FILTROS ===
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        exportador = st.selectbox("Exportador", ["Todos"] + sorted(df["Exportador"].dropna().unique().tolist()))
    with col_f2:
        importador = st.selectbox("Importador", ["Todos"] + sorted(df["Importador"].dropna().unique().tolist()))
    with col_f3:
        estado = st.selectbox("Estado", ["Todos"] + sorted(df["Estado"].dropna().unique().tolist()))
    with col_f4:
        fecha_referencia = st.date_input("Fecha base", value=datetime(2025, 6, 25))

    df["Dias_al_Vencimiento"] = (df["Fecha_Vencimiento"] - pd.to_datetime(fecha_referencia)).dt.days
    df = df[df["Dias_al_Vencimiento"] >= 0]  # Eliminar facturas ya vencidas
    df["Riesgo"] = df["Score Riesgo"].apply(lambda x: "Muy Bajo" if x >= 9 else "Bajo" if x >= 7 else "Medio" if x >= 5 else "Alto" if x >= 3 else "Muy Alto")

    if archivo_tasas:
        tasas_df = pd.read_excel(archivo_tasas).set_index("Riesgo")
        def buscar_tasa(riesgo, dias):
            if pd.isna(riesgo) or riesgo not in tasas_df.index: return None
            for plazo in [30, 60, 90, 120, 150]:
                if dias <= plazo:
                    return tasas_df.loc[riesgo, f"{plazo} dias"]
            return tasas_df.loc[riesgo, "150 dias"]
        df["Tasa Aplicada"] = df.apply(lambda row: buscar_tasa(row["Riesgo"], row["Dias_al_Vencimiento"]), axis=1)
        df["Tasa Aplicada"] = df["Tasa Aplicada"] / 100

    df_filtrado = df.copy()
    if exportador != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Exportador"] == exportador]
    if importador != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Importador"] == importador]
    if estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Estado"] == estado]

    # === MÉTRICAS ===
    total_monto = df_filtrado["Valor Factura (USD)"].sum()
    facturas_financiables = df_filtrado[df_filtrado["Estado"].isin(["Financiada", "En Proceso", "Rechazada"])]
    monto_facturas_financiables = facturas_financiables["Valor Factura (USD)"].sum()

    financiamiento_aprobado = df_filtrado[df_filtrado["Estado"] == "Financiada"]["Monto Financiado (USD)"].sum()
    financiamiento_rechazado = df_filtrado[df_filtrado["Estado"] == "Rechazada"]["Valor Factura (USD)"].sum()
    financiamiento_en_proceso = df_filtrado[df_filtrado["Estado"] == "En Proceso"]["Valor Factura (USD)"].sum()
    porcentaje_financiado_sobre_total = financiamiento_aprobado / total_monto if total_monto > 0 else 0

    porcentaje_en_proceso = financiamiento_en_proceso / financiamiento_aprobado if financiamiento_aprobado > 0 else 0

    tasa_promedio = df_filtrado[df_filtrado["Estado"] == "Financiada"]["Tasa Aplicada"].mean()
    tasa_maxima = df_filtrado[df_filtrado["Estado"] == "Financiada"]["Tasa Aplicada"].max()
    tasa_minima = df_filtrado[df_filtrado["Estado"] == "Financiada"]["Tasa Aplicada"].min()

    plazo_promedio = df_filtrado[df_filtrado["Estado"] == "Financiada"]["Dias_al_Vencimiento"].mean()
    plazo_maximo = df_filtrado[df_filtrado["Estado"] == "Financiada"]["Dias_al_Vencimiento"].max()
    plazo_minimo = df_filtrado[df_filtrado["Estado"] == "Financiada"]["Dias_al_Vencimiento"].min()

    total_valor_pagado = df_filtrado[df_filtrado["Estado"] == "Financiada"].groupby("Estado de Pago")["Monto Financiado (USD)"].sum()
    porcentaje_pagadas = total_valor_pagado.get("Pagada", 0) / financiamiento_aprobado if financiamiento_aprobado > 0 else 0
    porcentaje_atrasadas = total_valor_pagado.get("Atrasada", 0) / financiamiento_aprobado if financiamiento_aprobado > 0 else 0
    porcentaje_morosas = total_valor_pagado.get("Morosa", 0) / financiamiento_aprobado if financiamiento_aprobado > 0 else 0
    porcentaje_impagas = total_valor_pagado.get("Impaga", 0) / financiamiento_aprobado if financiamiento_aprobado > 0 else 0
    porcentaje_vigentes = total_valor_pagado.get("Vigente", 0) / financiamiento_aprobado if financiamiento_aprobado > 0 else 0

    # MÉTRICAS VISUALES
    col_a, col_b, col_c, col_d, col_e, col_f = st.columns(6)
    col_a.metric("Monto total de facturas", f"${total_monto:,.0f}")
    col_b.metric("Facturas Financiables", f"${monto_facturas_financiables:,.0f}")
    col_c.metric("Financiamiento aprobado", f"${financiamiento_aprobado:,.0f}")
    col_d.metric("Financiamiento rechazado", f"${financiamiento_rechazado:,.0f}")
    col_e.metric("Financiamiento en proceso", f"${financiamiento_en_proceso:,.0f}")
    col_f.metric("% Financiado sobre total", f"{porcentaje_financiado_sobre_total:.1%}")

    col_f1, col_f2, col_f3, col_f4, col_f5, col_f6 = st.columns(6)
    col_f1.metric("% Vigentes (sobre montos)", f"{porcentaje_vigentes:.1%}")
    col_f2.metric("% Pagadas (sobre montos)", f"{porcentaje_pagadas:.1%}")
    col_f3.metric("% Atrasadas (sobre montos)", f"{porcentaje_atrasadas:.1%}")
    col_f4.metric("% Morosas (sobre montos)", f"{porcentaje_morosas:.1%}")
    col_f5.metric("% Impagas (sobre montos)", f"{porcentaje_impagas:.1%}")
    col_f6.metric("% En Proceso (sobre montos)", f"{porcentaje_en_proceso:.1%}")

    col_t1, col_t2, col_t3, col_t4, col_t5, col_t6 = st.columns(6)
    col_t1.metric("Tasa promedio", f"{tasa_promedio:.2%}" if pd.notna(tasa_promedio) else "N/A")
    col_t2.metric("Tasa máxima", f"{tasa_maxima:.2%}" if pd.notna(tasa_maxima) else "N/A")
    col_t3.metric("Tasa mínima", f"{tasa_minima:.2%}" if pd.notna(tasa_minima) else "N/A")
    col_t4.metric("Plazo promedio", f"{plazo_promedio:.0f} días" if pd.notna(plazo_promedio) else "N/A")
    col_t5.metric("Plazo máximo", f"{plazo_maximo:.0f} días" if pd.notna(plazo_maximo) else "N/A")
    col_t6.metric("Plazo mínimo", f"{plazo_minimo:.0f} días" if pd.notna(plazo_minimo) else "N/A")

# === GRÁFICOS COMPARATIVOS ===
st.markdown("## Visualización Comparativa de Riesgo y Tasas")
col_g1, col_g2, col_g3 = st.columns([1, 1, 1])

with col_g1:
    with st.container(border=True, height=400):
        riesgo_group = df_filtrado.groupby("Riesgo")["Valor Factura (USD)"].agg(["sum", "count"]).reset_index()
        riesgo_group.columns = ["Riesgo", "Monto", "Cantidad"]
        riesgo_group = riesgo_group.sort_values(by="Monto", ascending=False)
        total_riesgo = riesgo_group["Monto"].sum()

        for _, row in riesgo_group.iterrows():
            porcentaje = row["Monto"] / total_riesgo if total_riesgo > 0 else 0
            st.markdown(f"<span style='font-size:13px'><strong>{row['Riesgo']}</strong> | {int(row['Cantidad'])} facturas | USD {row['Monto']:,.0f} ({porcentaje:.1%})</span>", unsafe_allow_html=True)
            st.progress(porcentaje)

with col_g2:
    with st.container(border=True, height=400):
        if archivo_tasas:
            tasas_long = tasas_df.reset_index().melt(id_vars="Riesgo", var_name="Plazo", value_name="Tasa")
            fig_tasa_riesgo_plazo = px.line(tasas_long, x="Plazo", y="Tasa", color="Riesgo", markers=True,
                title="Estructura de Tasas por Plazo y Riesgo")
            fig_tasa_riesgo_plazo.update_layout(height=360, margin=dict(t=40))
            st.plotly_chart(fig_tasa_riesgo_plazo, use_container_width=True, config={"staticPlot": True})

with col_g3:
    with st.container(border=True, height=400):
        if archivo_tasas:
            promedio_tasa = tasas_df.mean(axis=1).reset_index()
            promedio_tasa.columns = ["Riesgo", "Tasa Promedio"]
            riesgo_orden = ["Muy Bajo", "Bajo", "Medio", "Alto", "Muy Alto"]
            promedio_tasa["Orden"] = promedio_tasa["Riesgo"].apply(lambda x: riesgo_orden.index(x) if x in riesgo_orden else 99)
            promedio_tasa = promedio_tasa.sort_values("Orden")

            fig_tasa_promedio = px.bar(promedio_tasa, x="Riesgo", y="Tasa Promedio", color="Riesgo",
                title="Tasa Promedio por Nivel de Riesgo", text="Tasa Promedio")
            fig_tasa_promedio.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_tasa_promedio.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', height=360, margin=dict(t=40))
            st.plotly_chart(fig_tasa_promedio, use_container_width=True, config={"staticPlot": True})

# === GRÁFICOS DE DESTINO Y FLUJO ===
st.markdown("## Visualización de Destino y Flujo")
col_d1, col_d2, col_d3 = st.columns([1, 1, 1])

with col_d1:
    with st.container(border=True, height=400):
        productos = df_filtrado[df_filtrado["Estado"] == "Financiada"].groupby("Producto")["Valor Factura (USD)"].sum().reset_index()
        productos = productos.sort_values("Valor Factura (USD)", ascending=False)
        fig_productos = px.pie(productos, names="Producto", values="Valor Factura (USD)",
            title="Productos de Facturas Financiadas", hole=0.4)
        fig_productos.update_layout(height=320, margin=dict(t=40))
        st.plotly_chart(fig_productos, use_container_width=True, config={"staticPlot": True})

with col_d2:
    with st.container(border=True, height=400):
        destino_all = df_filtrado[df_filtrado["Estado"] == "Financiada"].groupby("País de Destino")["Valor Factura (USD)"].sum().reset_index()
        destino_all = destino_all.sort_values("Valor Factura (USD)", ascending=False)
        fig_destino_all = px.pie(destino_all, names="País de Destino", values="Valor Factura (USD)",
            title="País de Destino de Facturas Financiadas", hole=0.4)
        fig_destino_all.update_layout(height=320, margin=dict(t=40))
        st.plotly_chart(fig_destino_all, use_container_width=True, config={"staticPlot": True})

with col_d3:
    with st.container(border=True, height=400):
        flujo = df_filtrado[df_filtrado["Estado"] == "Financiada"].copy()

        col1, col2 = st.columns(2)
        with col1:
            periodo = st.selectbox("Visualización de Vencimiento", ["Mensual", "Semanal", "Diaria"], key="periodo_vencimiento")
        with col2:
            fecha_min = pd.to_datetime(flujo["Fecha_Vencimiento"].min())
            fecha_max = pd.to_datetime(flujo["Fecha_Vencimiento"].max())
            rango = st.date_input("Rango de Fechas", [fecha_min, fecha_max], key="rango_flujo")

        flujo = flujo[(flujo["Fecha_Vencimiento"] >= pd.to_datetime(rango[0])) & (flujo["Fecha_Vencimiento"] <= pd.to_datetime(rango[1]))]

        if periodo == "Mensual":
            flujo["Período"] = flujo["Fecha_Vencimiento"].dt.to_period("M").astype(str)
        elif periodo == "Semanal":
            flujo["Período"] = flujo["Fecha_Vencimiento"].dt.to_period("W").apply(lambda x: x.start_time.strftime('%b %d'))
        else:
            flujo["Período"] = flujo["Fecha_Vencimiento"].dt.strftime("%Y-%m-%d")

        flujo_group = flujo.groupby("Período")["Monto Financiado (USD)"].sum().reset_index()
        fig_flujo = px.bar(flujo_group, x="Período", y="Monto Financiado (USD)",
            title=f"Flujo de Vencimiento ({periodo}) de Facturas Financiadas")
        fig_flujo.update_layout(height=320, margin=dict(t=40), xaxis_tickangle=0, xaxis_title=None)
        st.plotly_chart(fig_flujo, use_container_width=True, config={"staticPlot": True})

# === TABLA DE DETALLE ===
st.markdown("## Detalle de facturas")
st.dataframe(df_filtrado, use_container_width=True)

# === DESCARGA ===
@st.cache_data
def convertir_excel(df):
    output = BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Facturas')
    except ImportError:
        with pd.ExcelWriter(output) as writer:
            df.to_excel(writer, index=False, sheet_name='Facturas')
    output.seek(0)
    return output

excel_filtrado = convertir_excel(df_filtrado)
st.download_button(
    label="Descargar Excel filtrado",
    data=excel_filtrado,
    file_name="facturas_filtradas.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
