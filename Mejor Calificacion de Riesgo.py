import io
import os
import re
import sys
import webbrowser
import numpy as np
import pandas as pd
import requests
import streamlit as st

# =========================================================================
# CONFIGURACIÓN GENERAL Y OPTIMIZACIÓN MÓVIL
# =========================================================================
st.set_page_config(
    page_title="Mejor Calificación de Riesgo",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 0.5rem; padding-bottom: 1rem;}
    </style>
""",
    unsafe_allow_html=True,
)

if "browser_opened" not in st.session_state:
  st.session_state["browser_opened"] = True
  try:
    webbrowser.open("http://localhost:8501")
  except Exception:
    pass

if st.button("🔄 Actualizar Datos"):
  st.rerun()

FILE_ID = "1ZtmezQ9fQfpUmpRdHa66Fp0j733j5qwv"
URL_DRIVE_DOWNLOAD = (
    f"https://drive.google.com/uc?export=download&id={FILE_ID}"
)

# =========================================================================
# DICCIONARIO DE EQUIVALENCIAS Y LÓGICA DE CONVERSIÓN
# =========================================================================
TABLA_EQUIVALENCIAS = {
    "AAA": 100.0,
    "AAA-": 95.0,
    "AA+": 90.0,
    "AA": 85.0,
    "AA-": 80.0,
    "A+": 75.0,
    "A": 70.0,
    "A-": 65.0,
    "BBB+": 60.0,
    "BBB": 55.0,
    "BBB-": 50.0,
    "BB+": 45.0,
    "BB": 40.0,
    "BB-": 35.0,
    "B+": 30.0,
    "B": 25.0,
    "B-": 20.0,
    "C": 15.0,
    "D": 5.0,
    "E": 0.0,
}


def obtener_puntaje_nota(nota):
  if pd.isna(nota) or str(nota).strip().upper() in ["N/A", "", "NAN", "NONE"]:
    return np.nan

  nota_limpia = str(nota).strip().upper()
  nota_limpia = re.sub(r'[*.]', '', nota_limpia)

  if '/' in nota_limpia:
    partes = [p.strip() for p in nota_limpia.split('/') if p.strip()]
    puntajes = []
    for p in partes:
      if p in TABLA_EQUIVALENCIAS:
        puntajes.append(TABLA_EQUIVALENCIAS[p])
    return np.mean(puntajes) if puntajes else np.nan

  return TABLA_EQUIVALENCIAS.get(nota_limpia, np.nan)


@st.cache_data(ttl=300)
def cargar_datos_desde_drive():
  try:
    response = requests.get(URL_DRIVE_DOWNLOAD, timeout=30)
    response.raise_for_status()
    excel_bytes = io.BytesIO(response.content)
    xls = pd.ExcelFile(excel_bytes)

    df_bancos = (
        pd.read_excel(xls, sheet_name='Bancos')
        if 'Bancos' in xls.sheet_names
        else pd.DataFrame()
    )
    df_coop = (
        pd.read_excel(xls, sheet_name='Cooperativas')
        if 'Cooperativas' in xls.sheet_names
        else pd.DataFrame()
    )

    return df_coop, df_bancos
  except Exception as e:
    st.error(
        f'❌ Error al descargar o leer el archivo Excel desde Google Drive:'
        f' {e}'
    )
    return None, None


df_coop_raw, df_bancos_raw = cargar_datos_desde_drive()

# =========================================================================
# TÍTULO PRINCIPAL
# =========================================================================
st.title('🏆 Mejor Calificación de Riesgo')

if df_coop_raw is None or df_bancos_raw is None:
  st.stop()

# =========================================================================
# ESTRUCTURA DE PESTAÑAS Y PROCESAMIENTO
# =========================================================================
tab_coop, tab_bancos = st.tabs(['🏦 Cooperativas (Segmento 1)', '🏛️ Bancos'])


def procesar_vista_tab(df_raw, tipo_entidad):
  if df_raw.empty:
    st.warning(f'No hay datos registrados para {tipo_entidad}.')
    return

  columnas_base = [c for c in df_raw.columns if not c.startswith('AL ')]

  if tipo_entidad == 'Cooperativas':
    columnas_base = [c for c in columnas_base if c.upper() != 'SEGMENTO']

  if 'INSTITUCIÓN FINANCIERA' in columnas_base:
    columnas_base.remove('INSTITUCIÓN FINANCIERA')
    columnas_base = ['INSTITUCIÓN FINANCIERA'] + columnas_base

  columnas_periodos = [c for c in df_raw.columns if c.startswith('AL ')]

  df_puntajes = df_raw.copy()
  for col in columnas_periodos:
    df_puntajes[f'PUNTS_{col}'] = df_raw[col].apply(obtener_puntaje_nota)

  st.subheader(f'📊 Ranking General de {tipo_entidad}')
  col_filtro, _ = st.columns([2, 2])
  with col_filtro:
    opciones_periodo = {
        'Último periodo (Corte más reciente)': 1,
        'Últimos 2 periodos': 2,
        'Últimos 3 periodos': 3,
        'Todos los periodos': len(columnas_periodos),
    }
    periodo_sel = st.radio(
        f'Seleccione el horizonte de evaluación para el Ranking de'
        f' {tipo_entidad}:',
        options=list(opciones_periodo.keys()),
        horizontal=True,
    )

  num_periodos = opciones_periodo[periodo_sel]
  cols_evaluadas = columnas_periodos[-num_periodos:]
  cols_puntajes_evaluados = [f'PUNTS_{c}' for c in cols_evaluadas]

  df_ranking = df_raw.copy()
  df_ranking['Puntaje Promedio'] = df_puntajes[
      cols_puntajes_evaluados
  ].mean(axis=1, skipna=True)
  df_ranking = df_ranking.sort_values(
      by='Puntaje Promedio', ascending=False
  ).reset_index(drop=True)

  m1, m2, m3 = st.columns(3)

  entidades_excluidas = (
      'CORPORACIÓN NACIONAL DE FINANZAS POPULARES|CAJA CENTRAL FINANCOOP'
  )
  df_lideres = df_ranking[
      ~df_ranking['INSTITUCIÓN FINANCIERA'].str.contains(
          entidades_excluidas, case=False, na=False
      )
  ]

  entidad_top = (
      df_lideres.iloc[0]['INSTITUCIÓN FINANCIERA']
      if not df_lideres.empty
      else 'N/A'
  )
  puntaje_top = (
      df_lideres.iloc[0]['Puntaje Promedio'] if not df_lideres.empty else 0.0
  )
  promedio_general = df_ranking['Puntaje Promedio'].mean()

  with m1:
    st.markdown(
        f"""
        <div style="background-color: #0E1117; padding: 12px; border-radius: 8px; border: 1px solid #262730;">
            <span style="font-size: 0.85rem; color: #FAFAFA; font-weight: 500;">🥇 Líder del Ranking</span>
            <div style="font-size: 1.15rem; font-weight: bold; color: #FFFFFF; word-wrap: break-word; white-space: normal; line-height: 1.3; margin-top: 4px; margin-bottom: 6px;">
                {entidad_top}
            </div>
            <span style="background-color: #1E3A2B; color: #4ADE80; padding: 2px 8px; border-radius: 10px; font-size: 0.85rem; font-weight: bold;">
                ↑ {puntaje_top:.1f} pts
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

  m2.metric(
      '📈 Promedio Sectorial',
      f'{promedio_general:.1f} pts' if pd.notna(promedio_general) else 'N/A',
  )
  m3.metric('🏢 Total Entidades Evaluadas', len(df_ranking))

  columnas_mostrar = columnas_base + columnas_periodos + ['Puntaje Promedio']

  configuracion_columnas = {
      'INSTITUCIÓN FINANCIERA': st.column_config.TextColumn(
          'INSTITUCIÓN FINANCIERA', width='medium'
      ),
      'FIRMA CALIFICADORA DE RIESGO': st.column_config.TextColumn(
          'FIRMA CALIFICADORA DE RIESGO', width='small'
      ),
  }

  st.dataframe(
      df_ranking[columnas_mostrar].style.format(
          {'Puntaje Promedio': '{:.1f}'}, na_rep='N/A'
      ),
      use_container_width=True,
      height=380,
      hide_index=True,
      column_config=configuracion_columnas,
  )

  st.markdown('---')
  st.subheader(f'🔍 Búsqueda e Historial Individual de {tipo_entidad}')
  st.caption(
      'Escriba o seleccione el nombre de la entidad en la casilla inferior'
      ' para autocompletar y filtrar en tiempo real.'
  )

  lista_entidades = sorted(df_raw['INSTITUCIÓN FINANCIERA'].dropna().unique())
  entidad_seleccionada = st.selectbox(
      f'Ingrese o seleccione el nombre de la institución ({tipo_entidad}):',
      options=['-- Seleccione una entidad --'] + lista_entidades,
      index=0,
      key=f'search_{tipo_entidad}',
  )

  if entidad_seleccionada != '-- Seleccione una entidad --':
    registro_entidad = df_raw[
        df_raw['INSTITUCIÓN FINANCIERA'] == entidad_seleccionada
    ]
    registro_puntajes = df_puntajes[
        df_puntajes['INSTITUCIÓN FINANCIERA'] == entidad_seleccionada
    ]

    if not registro_entidad.empty:
      st.success(f'📌 Resultados para: **{entidad_seleccionada}**')

      row_entidad = registro_entidad.iloc[0]
      row_puntajes = registro_puntajes.iloc[0]

      col_a, col_b, col_c = st.columns(3)
      with col_a:
        calificadora = row_entidad.get('FIRMA CALIFICADORA DE RIESGO', 'N/A')
        st.info(f'**Firma Calificadora:**\n\n{calificadora}')
      with col_b:
        ult_col = columnas_periodos[-1]
        ult_nota = row_entidad[ult_col]
        st.info(f'**Última Calificación ({ult_col}):**\n\n### {ult_nota}')
      with col_c:
        ult_pts = row_puntajes[f'PUNTS_{ult_col}']
        pts_texto = f'{ult_pts:.1f} / 100' if pd.notna(ult_pts) else 'N/A'
        st.info(f'**Puntaje Numérico Actual:**\n\n### {pts_texto}')

      st.markdown(
          '##### 📋 Historial Completo de Calificaciones por Periodo'
      )
      df_historial = pd.DataFrame({
          'Periodo de Corte': columnas_periodos,
          'Calificación de Riesgo': [
              row_entidad[c] for c in columnas_periodos
          ],
          'Puntaje Equivalente (0-100)': [
              row_puntajes[f'PUNTS_{c}'] for c in columnas_periodos
          ],
      })

      st.dataframe(
          df_historial.style.format(
              {'Puntaje Equivalente (0-100)': '{:.1f}'}, na_rep='N/A'
          ),
          use_container_width=True,
          hide_index=True,
          column_config={
              'Periodo de Corte': st.column_config.TextColumn(
                  'Periodo de Corte', width='medium'
              )
          },
      )


with tab_coop:
  procesar_vista_tab(df_coop_raw, 'Cooperativas')

with tab_bancos:
  procesar_vista_tab(df_bancos_raw, 'Bancos')

if __name__ == '__main__':
  if 'streamlit' not in sys.argv[0]:
    os.system(f'streamlit run "{__file__}" --server.port 8501')