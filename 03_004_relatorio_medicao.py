import os
import re
import pickle
import pandas as pd
import numpy as np
from unidecode import unidecode
from datetime import datetime, timedelta


### INICIALIZAÇÃO
with open('../termo_aditivo.pickle', 'rb') as arquivo:
    termo_aditivo = pickle.load(arquivo)

with open('tlp.pickle', 'rb') as arquivo:
    tlp = pickle.load(arquivo)

dataframes = []
df_deficit_prof = []

# Exclui os médicos de unidade tipo AMA que são contabilizados pela planilha de plantões
termo_aditivo = termo_aditivo[~((termo_aditivo['TIPO_UNIDADE'] == 'AMA') & (termo_aditivo['CAT_PROF'].str.contains('MEDICO')))].reset_index(drop=True)


### FUNÇÕES
def str_to_time(time: str) -> timedelta:  # Converte uma string 'HH:MM' em um período datatime em segundos
    hours, minutes = map(int, time.split(':'))
    return timedelta(hours=hours, minutes=minutes)


def time_to_str(time):  # Converte um período datatime em segundos em uma string 'HH:MM'
    return f'{int(time.total_seconds() // 3600):02d}:{int((time.total_seconds() % 3600) // 60):02d}'


### EXECUÇÃO

# Converte as colunas de horário no formato string para datetime
colunas_horarios = ['NU_CARGA_HORARIA', 'deficit_eq_min_horas']  # Lista para armazenar os nomes das colunas que precisam ser convertidas
for col in colunas_horarios: # Converte as colunas datetime novamente para string
    tlp[col] = tlp[col].apply(lambda x: timedelta(hours=int(x.split(':')[0]), minutes=int(x.split(':')[1])) if pd.notna(x) else x)

#
grupos_ta = termo_aditivo.groupby(['index', 'TIPO_UNIDADE', 'TIPO_EQUIPE', 'CAT_PROF'])

for name, group in grupos_ta:
    ID = group['index'].iloc[0]
    TIPO_UNIDADE = group['TIPO_UNIDADE'].iloc[0]
    TIPO_EQUIPE = group['TIPO_EQUIPE'].iloc[0]
    CAT_PROF = group['CAT_PROF'].iloc[0]
    
    tlp_filtro = tlp[(tlp['index'] == ID) & \
                    (tlp['TIPO_UNIDADE'] == TIPO_UNIDADE) & \
                    (tlp['TIPO_EQUIPE'] == TIPO_EQUIPE) & \
                    (tlp['CAT_PROF'] == CAT_PROF)].reset_index(drop=True)
    
    jornada_mensal_ta = timedelta(hours=int(group['JORNADA_CONSULTA'].sum()))
    qtd_prof_hs_tlp = tlp_filtro['NU_CARGA_HORARIA'].sum()
    deficit_afast_30 = tlp_filtro['deficit_eq_min_horas'].sum()
    deficit_prof_hs = jornada_mensal_ta - (qtd_prof_hs_tlp - deficit_afast_30)
    group['qtd_prof_hs_tlp'] = qtd_prof_hs_tlp
    group['deficit_afast_30'] = deficit_afast_30
    group['deficit_prof_hs'] = deficit_prof_hs
    
    ta_tlp = pd.concat([group, tlp_filtro], axis=0)
    dataframes.append(ta_tlp)
    if deficit_prof_hs != timedelta(days=0):
        df_deficit_prof.append(ta_tlp)

#
termo_aditivo = pd.concat(dataframes, ignore_index=True)
df_deficit_prof = pd.concat(df_deficit_prof, ignore_index=True)

colunas_horarios = ['NU_CARGA_HORARIA', 'deficit_eq_min_horas', 'qtd_prof_hs_tlp', 'deficit_afast_30', 'deficit_prof_hs']
for col in colunas_horarios: # Converte as colunas datetime novamente para string
    termo_aditivo[col] = termo_aditivo[col].apply(lambda x: time_to_str(x) if pd.notna(x) else x)
    df_deficit_prof[col] = df_deficit_prof[col].apply(lambda x: time_to_str(x) if pd.notna(x) else x)

termo_aditivo.to_excel('log_002_medicao_equipe_completo.xlsx', index=False)
df_deficit_prof.to_excel('log_003_medicao_equipe_inconsistencias.xlsx', index=False)

#
tlp_contabilizada = termo_aditivo[pd.isna(termo_aditivo['UNIDADE'])]
excluidos_tlp = tlp[~(tlp['PROF_ID'].isin(tlp_contabilizada['PROF_ID']))]
excluidos_tlp.to_excel('log_004_erros_prof_nao_contabilizados.xlsx', index=False)