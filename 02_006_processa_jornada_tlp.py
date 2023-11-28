import pandas as pd
import numpy as np
import pickle
import re
from unidecode import unidecode
import numpy as np
from datetime import timedelta
from datetime import datetime

with open('../tlp.pickle', 'rb') as arquivo:
    tlp = pickle.load(arquivo)

tlp = tlp.reset_index(drop=True)
tlp = tlp.assign(
    jornada_tlp='',
    tlpDOM='', tlpSEG='', tlpTER='', tlpQUA='', tlpQUI='', tlpSEX='', tlpSAB='',  # (DOM, SEG, TER, QUA, QUI, SEX, SAB) EXCLUI
    tlpDom='', tlpSeg='', tlpTer='', tlpQua='', tlpQui='', tlpSex='', tlpSab='',  # (Dom, Seg, Ter, Qua, Qui, Sex, Sab)
    tlpiDom='', tlpiSeg='', tlpiTer='', tlpiQua='', tlpiQui='', tlpiSex='', tlpiSab='',  # Intervalos (almoço, pausa) EXCLUI
    tlpji0='00:00',  # jornada sem intervalo EXCLUI
    tlpji15='00:00',  # jornada + intervalos de 15 minutos EXCLUI
    tlpji60='00:00',  # jornada + intervalos diferentes de 15 minutos EXCLUI
    tlpji1='00:00',   # jornada + todos os intervalos EXCLUI
    jornada_usada_tlp='',
    jornada_mensal_tlp='00:00',  # A jornada dentre ji0, ji15, ji60 e ji1 que for igual a jornada TLP, sem levar em consideraçAo os minutos
    previdencia='00:00', maternidade='00:00', atestado='00:00', gala='00:00', nojo='00:00', paternidade='00:00', ferias='00:00',
    data_previdencia='', data_maternidade='', data_atestado='', data_gala='', data_nojo='', data_paternidade = '', data_ferias='',
    deficit_previdencia=0, deficit_maternidade=0, deficit_atestado=0, deficit_gala=0, deficit_nojo=0, deficit_paternidade=0, deficit_ferias=0, 
    deficit_total_horas='00:00',
    deficit_total_prof=0,
    defict_total_jornada='00:00',
    deficit_contratacao=0,
    deficit_contrat_horas='00:00',
    deficit_eq_min=0,
    deficit_eq_min_horas='00:00',
)

original_columns = tlp.columns.tolist()  # Guarda a ordem original das colunas

### LISTAS DE AJUSTES, REAJUSTAR A CADA MÊS

dias_uteis_semana = [0, 5, 5, 4, 3, 4, 4]  # Quantidade de dias uteis para cada dia da semana: 'Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab'
dias_totais_semana = [5, 5, 5, 4, 4, 4, 4]  # Dias uteis + feriados
INICIO_DO_MES = datetime(2023, 10, 1)
FINAL_DO_MES = datetime(2023, 10, 31)

### VARIAVEIS

tlp_jornada_nao_semanal = pd.DataFrame(columns=['nome', 'dia_semana', 'jornada', 'intervalo'])
dias_semana = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab']
dias_semana_upper = ['DOM', 'SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB']
lancamentos_jornada_tlp = ''  # Adiciona todos os valores da coluna 'HR_TRABALHO' da TLP e posteriormente cria uma lista com os valores únicos da coluna [08:00, SEG, 12x36] etc
 
### FUNÇÕES


def str_to_time(time: str) -> timedelta:  # Converte uma string 'HH:MM' em um período datatime em segundos
    hours, minutes = map(int, time.split(':'))
    return timedelta(hours=hours, minutes=minutes)


def time_to_str(time):  # Converte um período datatime em segundos em uma string 'HH:MM'
    total_seconds = time.total_seconds()
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f'{int(hours):02d}:{int(minutes):02d}'


def time_difference(hor_final, hor_inicial):  # Calcula o período de horas/minutos entre dois períodos no formato 'HH:MM'
    hor_final = str_to_time(hor_final)
    hor_inicial = str_to_time(hor_inicial)
    if hor_final < hor_inicial: # Verifica se o período começa em um dia e termina no outro
        hor_final += timedelta(days=1)
    diff = hor_final - hor_inicial
    return time_to_str(diff)
  

def processa_jornada_tlp(row):
    """
    PROCESSO MUITO LONGO E COMPLEXO DE CONVERTER AS DIVERSAS JORNADAS DIGITADAS MANUALMENTE POR CADA UNIDADE NA TLP EM UM BANCO DE DADOS COERENTE.
    """
    # INICIALIZAÇÃO DE VARIÁVEIS

    # DEBUG
    if row['NM_PROFISSIONAL'] == 'FABRICIO FERNANDES DANTAS':
        pass    
    
    global lancamentos_jornada_tlp  # Lista de todas as jornadas
    JORNADA_TLP_REGEX = re.compile(r'[^A-Z0-9:/]')  # Apaga os caracteres especiais '.', '(', dentre outros
    jornada_tlp = str(row['HR_TRABALHO'])
    jornada_semanal = row['NU_CARGA_HORARIA']
    jornada_periodica = False

    # VERIFICA OS DADOS QUE NÃO DEVEM SER PROCESSADOS E PASSA PARA A PRÓXIMA LINHA
    if pd.notna(row['ESCALA']):  # Considera 26:00 de jornada mensal para cada 06:00 de jornada semanal
        row['jornada_mensal_tlp'] = time_to_str(((str_to_time(row['NU_CARGA_HORARIA']))/6)*26)
        return row
    if jornada_semanal == '01:00':  # A jornada mensal tlp padrão já é 00:00
        jornada_semanal = '00:00'
        row['NU_CARGA_HORARIA'] = '00:00'
    if jornada_semanal == '00:00':
        return row

    ### FORMAÇÃO DA JORNADA DE TRABALHO NA TLP ###

    # FORMATA A COLUNA DA TLP 'HR_TRABALHO'
    jornada_tlp = re.sub(r'(\d{2}:)(\d{2})(:\d{2})', r'\1\2', jornada_tlp)  # 07:00:00 > 07:00
    jornada_tlp = re.sub(r'(\d{1}:\d{2}):', r'0\1', jornada_tlp)  # 8:00: > 08:00
    jornada_tlp = re.sub(r'(\d{2}:) (\d{2})', r'\1\2', jornada_tlp)  # 07: 00 > 07:00
    jornada_tlp = re.sub(r'(\d{1});(\d{1})', r'\1:\2', jornada_tlp)  # 07;00 > 07:00
    jornada_tlp = jornada_tlp.replace('/', ' / ')  # Mantem / para manter os blocos de jornada 'SEG 07:00 /' conforme a intençao original da TLP
    jornada_tlp = (unidecode(jornada_tlp)).upper()  # Apaga acentuaçao e deixa a jornada em caixa alta
    jornada_tlp = ' '.join((JORNADA_TLP_REGEX.sub(' ', jornada_tlp)).split())  # Apaga os espaços duplos, mantém apenas os caracteres de interesse

    # ANALISE DE MARCAÇÕES UNICAS DEVE SER APLICADA A PARTIR DAQUI
        # 1 - TRABALHA A STRING COMPLETA DA JORNADA NESTE TRECHO
    
    # Formata os dados conforme a análise dos valores únicos do log de marcações únicas.
    replacements = {
        '::': ':',
        '6X1': 'SEG A SAB',
        '2 A 6': 'SEG A 6',
        '1A E 3A': '2X MES',
        '2 X': '2X',
        'QUINZENAL': '2X MES',
        ' VEZES': 'X',
        ' VEZ': 'X',
        'NA SEMANA': 'SEMANA',
        'ULTIMO SABADO': '',
        '/ INTERVALO': 'INTERVALO',
        '6ADAS': 'SEX',
        '6 FEIRA': 'SEX',
        ' A S ': ' '
    }
    for old, new in replacements.items():
        jornada_tlp = jornada_tlp.replace(old, new)

    # Formata os dias da semana em um único formato
    segunda = 'SEGUNDAS|SEGUNDA|2DEG|2A|2O'
    terca = 'TERCAS|TERCA|3DEG|3A|3O'
    quarta = 'QUARTAS|QUARTA|QUAR|4DEG|4A|4O'
    quinta = 'QUINTAS|QUINTA|QUIN|5DEG|5A|5O'
    sexta = 'SEXTAS|SEXTA|6DEG|6DEG|06A|6A|6O'
    sabado = 'SABADOS|SABADO|SABA'
    domingo = 'DOMINGO'
    jornada_tlp = re.sub(segunda, 'SEG', jornada_tlp) .replace('SEG:', 'SEG')
    jornada_tlp = re.sub(terca, 'TER', jornada_tlp).replace('TER:', 'TER')
    jornada_tlp = re.sub(quarta, 'QUA', jornada_tlp).replace('QUA:', 'QUA')
    jornada_tlp = re.sub(quinta, 'QUI', jornada_tlp).replace('QUI:', 'QUI')
    jornada_tlp = re.sub(sexta, 'SEX', jornada_tlp).replace('SEX:', 'SEX')
    jornada_tlp = re.sub(sabado, 'SAB', jornada_tlp).replace('SAB:', 'SAB')
    jornada_tlp = re.sub(domingo, 'DOM', jornada_tlp).replace('DOM:', 'DOM')

        # 2 - DIVIDE A STRING DA JORNADA PELOS CARACTERES DE ESPAÇO EM UMA LISTA E TRABALHA CADA ITEM INDIVIDUALMENTE

    jornada_tlp = list(jornada_tlp.split())  # Transforma a jornada em uma lista para realizar os ajustes por item

    # Lista de termos que devem ser excluídos
    exclusoes = ['EMAB', 'X000D', 'CONFORME', 'ESCALA', 'FOLGUISTA', 'FOLGISTA', 'APRENDIZ', 'PLANTONISTA', 'PLANT', 'UBS', 'MARINGA', 'TRINDADE', \
    'COBERTURA', 'NAN', 'POR', 'NO', 'AO', 'DE', 'FEIRAS', 'FEIRA', '@', r'MIN$', r'^DAS$', r'^AS$', r'^E$', r'^H$', r'^HS$', \
    r'^HRS$', r'^HOR$', r'^HORAS$', r'^DAS', r'^AS']

    # Itera por cada item da jornada e realiza as substituições e depois as exclusões
    for j in range(0, len(jornada_tlp)):
        # Substituições (A ordem de execuçAo deve ser observada):
        jornada_tlp[j] = re.sub(r'(\d{2}:\d{2})HRS', r'\1', jornada_tlp[j])  # 07:00HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{2}:\d{2})HS', r'\1', jornada_tlp[j])  # 07:00HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{2}:\d{2})HR', r'\1', jornada_tlp[j])  # 07:00HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{2}:\d{2})H', r'\1', jornada_tlp[j])  # 07:00H > 07:00
        jornada_tlp[j] = re.sub(r'(\d)HS(\d)', r'\1:\2', jornada_tlp[j])  # 7HS0 > 7:0
        jornada_tlp[j] = re.sub(r'(\d)H(\d)', r'\1:\2', jornada_tlp[j])  # 7H0 > 7:0
        jornada_tlp[j] = re.sub(r'(\d{2})HRS', r'\1:00', jornada_tlp[j])  # 07HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{2})HS', r'\1:00', jornada_tlp[j])  # 07HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{2})HR', r'\1:00', jornada_tlp[j])  # 07HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{2})H', r'\1:00', jornada_tlp[j])  # 07H > 07:00
        jornada_tlp[j] = re.sub(r'(\d{1})HRS', r'0\1:00', jornada_tlp[j])  # 7HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{1})HS', r'0\1:00', jornada_tlp[j])  # 7HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{1})HR', r'0\1:00', jornada_tlp[j])  # 7HS > 07:00
        jornada_tlp[j] = re.sub(r'(\d{1})H', r'0\1:00', jornada_tlp[j])  # 7H > 07:00
        jornada_tlp[j] = re.sub(r'(\d{2}:)$', r'\1' + '00', jornada_tlp[j])  # 07 > 07:00
        jornada_tlp[j] = re.sub(r'(\d{2}:\d{2})(\d{2}:\d{2})', r'\1 \2', jornada_tlp[j])  # 07:0013:00 > 07:00 13:00
        jornada_tlp[j] = re.sub(r'(\d{2}:)(\d{2})(:\d{2})', r'\1\2', jornada_tlp[j])  # 13:15:00 > 13:15
        jornada_tlp[j] = re.sub(r'^(\d{1}:\d{2})$', r'0\1', jornada_tlp[j])  # string completa '7:00' > 07:00
        jornada_tlp[j] = re.sub(r'^(\d{2}:\d{1})$', r'\g<1>0', jornada_tlp[j])
        jornada_tlp[j] = re.sub(r'^(\d{2})$', r'\1:00', jornada_tlp[j])  # string completa '07' > 07:00
        jornada_tlp[j] = re.sub(r'^(\d{1})$', r'0\1:00', jornada_tlp[j])  # string completa '7' > 07:00
        # Exclusões:
        for exclusao in exclusoes:
            jornada_tlp[j] = re.sub(exclusao, '', jornada_tlp[j])

        # 3 - CONCATENA NOVAMENTE A JORNADA E REALIZA NOVAS SUBSTITUIÇÕES

    jornada_tlp = ' '.join((' '.join(jornada_tlp)).split())  # Concatena a lista jornada, e concatena novamente com o método split para eliminar duplicadade de espaços

    # Ajustes finais após concatenar a lista jornada
    jornada_tlp = re.sub(r'(\d{2}:\d{2}) (\d{2}:\d{2}) INTERVALO (\d{2}:\d{2}) (\d{2}:\d{2})', r'\1 \3 \4 \2', jornada_tlp)  # 07:00 16:00 INTERVALO 12:00 13:00 > 07:00 12:00 13:00 16:00
    jornada_tlp = re.sub(r'(\d{2}:\d{2}) (\d{2}:\d{2}) ALMOCO (\d{2}:\d{2}) (\d{2}:\d{2})', r'\1 \3 \4 \2', jornada_tlp)
    jornada_tlp = re.sub(r'(\d{2}:\d{2}) A (\d{2}:\d{2})', r'\1 \2', jornada_tlp)  # 07:00 A 16:00 > 07:00 16:00 (Pois NAO é possível excluir ' A ')
    jornada_tlp = re.sub(r'(\d{2}:\d{2}) OU (\d{2}:\d{2}) (\d{2}:\d{2})', r'\1', jornada_tlp)  # 06:00 OU 06:00 'CONFORME ESCALA > 06:00
    jornada_tlp = re.sub(r'(\d{2}) (\d{2}) (\d{2}) (\d{2})', r'\1:\2 \3:\4', jornada_tlp)  # 07 00 16 00 > 07:00 16:00
    jornada_tlp = re.sub(r'(\d{2}) (\d{2}) (\d{2})', r'\1:\2 \3', jornada_tlp) # 07 00 16 > 07:00 16

    ### FIM DA FORMATAÇÃO DA JORNADA, VERIFICA OS ERROS ###

    # ERROS: Verifica se a jornada calculada está vazia. Exemplo: jornada_tlp = 'COBERTURA'
    if jornada_tlp == '':
        row['avisos'] += ' |TLP: JORNADA EM BRANCO'
        row['erros'] += ' |TLP_ESPELHO: SEM JORNADA'
        return row
    # ERROS: VERIFICA SE ALGUMA JORNADA QUE NAO SEJA DA ESCALA 12X36 PREVISTA OCORRE NO DOMINGO:
    if 'DOM' in jornada_tlp:
        row['erros'] += ' |TLP: JORNADA INESPERADA NO DOMINGO (REVER CODIGO)'
    # ERROS: VERIFICA SE EXISTE ALGUM HORÁRIO APÓS EXCLUIR OS CONJUNTOS COM QUATRO E DOIS HORÁRIOS
    jornada_solta = re.sub(r'(\d{2}:\d{2}) (\d{2}:\d{2}) (\d{2}:\d{2}) (\d{2}:\d{2})', '', jornada_tlp)
    jornada_solta = re.sub(r'(\d{2}:\d{2}) (\d{2}:\d{2})', '', jornada_solta)
    if ':' in jornada_solta:    
        row['erros'] += ' |TLP: HORARIO SOLTO AO PROCESSAR JORNADA (REVER CODIGO OU TLP)'
        row['erros'] += ' |TLP_ESPELHO: SEM JORNADA'

    ### CALCULA O PERÍODO DE TEMPO ENCONTRANDO A QUANTIDADE DE HORAS TRABALHADAS PELO PROFISSIONAL ###

    # Calcula a jornada no formato 07:00 12:00 13:00 16:00 retornando o período trabalhado e intervalo no formato 08:00_01:00
    lst_jornadas = re.findall(r'(\d{2}:\d{2}) (\d{2}:\d{2}) (\d{2}:\d{2}) (\d{2}:\d{2})', jornada_tlp) # Cria uma lista com todas as ocorrências da regex
    for k in range(0, len(lst_jornadas)): 
        jornada = time_difference(lst_jornadas[k][-1], lst_jornadas[k][0])  # Calcula o intervalo do primeiro e último horário
        intervalo = time_difference(lst_jornadas[k][2], lst_jornadas[k][1])  # Calcula o intervalo do segundo e terceiro horário
        jornada = time_difference(jornada, intervalo)  # Exclui o intervalo da jornada total
        lst_jornadas[k] = jornada + '_'+ intervalo  # Substitui a jornada completa pela calculada. Utiliza caractere '_' para nao recalcular o intervalo novamente
    # Substitui os valores originais pelos valores calculados aplicando a lista calculada no lugar das ocorrências
    jornada_tlp = re.sub(r'(\d{2}:\d{2}) (\d{2}:\d{2}) (\d{2}:\d{2}) (\d{2}:\d{2})', '{}', jornada_tlp).format(*lst_jornadas)

    # Calcula a jornada no formato 07:00 16:00 retornando o período trabalhado e intervalo no formato 09:00
    lst_jornadas = re.findall(r'(\d{2}:\d{2}) (\d{2}:\d{2})', jornada_tlp)
    for l in range(0, len(lst_jornadas)):
        jornada = time_difference(lst_jornadas[l][-1], lst_jornadas[l][0])
        lst_jornadas[l] = jornada
    jornada_tlp = re.sub(r'(\d{2}:\d{2}) (\d{2}:\d{2})', '{}', jornada_tlp).format(*lst_jornadas)

    jornada_tlp = jornada_tlp.replace('_', ' ')  # Após calcular todas as jornadas e intervalos, restaura a jornada

    ### DECOMPOEM DIAS DA SEMANA DA JORNADA ###

    # DECOMPOE OS PERÍODOS DE DIAS DA SEMANA NO FORMATO 'SEG-QUA' PARA 'SEG, TER, QUA'
    jornada_tlp = jornada_tlp.replace(' A ', '-').replace('5X2', 'SEG-SEX').replace('6X1', 'SEG-SAB').replace('SEG-DOM', 'DOM-SAB')  # SEG A QUA > SEG-QUA
    lista_dias = jornada_tlp.split()
    dias_expandidos = []
    for dia in lista_dias:
        if '-' in dia:
            start, end = dia.split('-')
            start_index = dias_semana_upper.index(start)
            end_index = dias_semana_upper.index(end)
            dias_expandidos.extend(dias_semana_upper[start_index:end_index+1])
        else:
            dias_expandidos.append(dia)
    jornada_tlp = ' '.join(dias_expandidos)

    ### ORDENA A JORNADA NO FORMATO 'PERIODO DIAS, HORARIOS' OU 'SEG TER 08:00' ###

    # Cria blocos com dias da semana e horários pois na TLP a ordem dos blocos varia por unidade
    horario = re.findall(r'((?:\d{2}:\d{2}\s*)+)', jornada_tlp)
    dias = re.findall(r'((?:[A-Z]{3}\s*)+)', jornada_tlp)

    # ERROS: COMPARA A QUANTIDADE DE BLOCOS, DEVE HAVER UM BLOCO DE HORÁRIO POR BLOCO DE DIAS
    if len(dias) != len(horario):
        if len(dias) == 0:
            row['avisos'] += ' |TLP: BLOCOS: APENAS HORARIOS'
        else:
            if len(horario) == 0:
                row['avisos'] += ' |TLP: BLOCOS: APENAS DIAS'
            elif len(dias) < len(horario):
                row['avisos'] += ' |TLP: BLOCOS: HORARIOS > DIAS'
            else:
                row['avisos'] += ' |TLP: BLOCOS: DIAS > HORARIOS'
            row['erros'] += ' |TLP_ESPELHO: SEM JORNADA'
            return row

    # DEBUG LOG_006 MARCACOES UNICAS
    # if row['NM_PROFISSIONAL'] == 'ROSANA MOREIRA FERRARI DOS SANTOS':
    #     pass
    # debug_jornada = jornada_tlp.split()
    # if 'QUI12:00' in debug_jornada:
    #     print(row['HR_TRABALHO'])
    #     pass

    lancamentos_jornada_tlp += ' ' + jornada_tlp  # Copia a jornada para a lista de jornadas
    jornada_tlp = '' # Limpa a jornada, que será reconstruída a partir das listas 'horario' e 'dias'

    # Reconstroi a jornada pelo índice de dias ['SEG', 'QUA QUI'] e horario ['04:00', '08:00 01:00'] > 'SEG 04:00 QUA QUI 08:00 01:00'
    for m in range(0, 7):  # Quantidade dias da semana para um caso hipotético de utilizaçAo máxima
        if len(dias) > m:
            jornada_tlp += ' '+dias[m]
        if len(horario) > m:
            jornada_tlp += ' '+horario[m]

    jornada_tlp = ' '.join(jornada_tlp.split())  # Apaga espaços duplos após reconstruir a jornada

    ### AUTO CORREÇAO ERROS ###

    # Cria uma lista com os horários únicos presentes na jornada e a quantidade de dias da semana na jornada tlp
    qtde_dias_semana = 0 
    qtde_horarios = []
    lst_jornada_tlp = jornada_tlp.split()  # Cria uma lista com os elementos da jornada e itera sobre ela
    for item in lst_jornada_tlp:
        if len(item) == 3:  # Armazena os dias da semana 'SEG TER' etc
            qtde_dias_semana += 1
        if ':' in item:  # Adiciona os horários
            qtde_horarios.append(item)
    qtde_horarios = list(set(qtde_horarios)) # Exclui jornadas repetidas

    # Encontra horários sem intervalo e cria os intervalo
    hora_sem_intervalo = [  # Horário único na jornada, Intervalo na jornada, Novo Horário
        ['09:00', '01:00', '08:00 01:00'],
        ['08:48', '99:99', '08:30'],
        ['11:00', '01:00', '10:00 01:00'],
        ['06:15', '00:15', '06:00 00:15'],
        ['05:15', '00:15', '05:00 00:15']
    ]
    for hora in hora_sem_intervalo:
        if hora[0] in qtde_horarios and hora[1] not in qtde_horarios:
            jornada_tlp = jornada_tlp.replace(hora[0], hora[2])
            horario_triplo = re.findall(r'(\d{2}:\d{2}) (\d{2}:\d{2}) (\d{2}:\d{2})', jornada_tlp)
            if horario_triplo:
                row['erros'] += ' |TLP: JORNADA DESFORMATADA DURANTE AUTOCORRECAO'
                jornada_tlp = jornada_tlp.replace(hora[2], hora[0])

    # Encontra horários sem dias da semana para determinada jornada semanal e atribui os dias da semana
    hora_sem_dias = [  # Jornada semanal, Jornada completa, Nova Jornada
        ['30:00', ['06:00 00:15', '06:15', '06:00'], 'SEG TER QUA QUI SEX 06:00 00:15'],
        ['40:00', ['08:00 01:00', '09:00', '08:00'], 'SEG TER QUA QUI SEX 08:00 01:00'],
        ['36:00', ['06:00 00:15', '06:15', '06:00'], 'SEG TER QUA QUI SEX SAB 06:00 00:15'],
        ['20:00', ['SEG 08:00 01:00 QUI 04:00 SEX 09:00'], 'SEG 08:00 01:00 QUI 04:00 SEX 08:00 01:00'] # Caso único
    ]
    for hora in hora_sem_dias:
        if jornada_semanal == hora[0] and jornada_tlp in hora[1]:
            jornada_tlp = hora[2]
            row['avisos'] =  row['avisos'].replace(' |TLP: BLOCOS: APENAS HORARIOS', '').replace(' |TLP: JORNADA EQUIVALENTE NAO ENCONTRADA', '')
    
    # Cria novos intervalos a partir de jornadas sem intervalo, desta vez especificando a jornada semanal
    hora_sem_intervalo_com_jornada = [  # Jornada semanal, Horário único na jornada, Intervalo na jornada, Novo Horário
        ['36:00', '10:00', '01:00', '09:00 01:00'],
        ['20:00', '08:00', '01:00', '07:00 01:00'],
        ['10:00', '12:00', '02:00', '10:00 02:00'],
        ['11:00', '02:45', '00:15', '02:45 00:15'],
        ['30:00', '05:45', '00:15', '05:45 00:15'],
        ['32:00', '02:15', '00:15', '02:00 00:15'],
        ['32:00', '02:15', '00:15', '02:00 00:15'],
        ['08:00', '02:30', '00:30', '02:00 00:30'],
        ['40:00', '07:00', '99:99', '08:00'],
        ['40:00', '02:00', '99:99', '01:00'] # Alguns casos únicos
    ]
    for hora in hora_sem_intervalo_com_jornada:
        if jornada_semanal == hora[0] and hora[1] in qtde_horarios and hora[2] not in qtde_horarios:
            jornada_tlp = jornada_tlp.replace(hora[1], hora[3])
            horario_triplo = re.findall(r'(\d{2}:\d{2}) (\d{2}:\d{2}) (\d{2}:\d{2})', jornada_tlp)
            if horario_triplo:
                row['erros'] += ' |TLP: JORNADA DESFORMATADA DURANTE AUTOCORRECAO'
                jornada_tlp = jornada_tlp.replace(hora[3], hora[1])

    ### ATRIBUIÇÃO DE JORNADA ###

    # DISTRIBUI OS DIAS QUE O FUNCIONÁRIO TRABALHA NAS COLUNAS CORRESPONDENTES DE CADA DIA DA SEMANA, JORNADA, INTERVALOS
    for i, dia in enumerate(dias_semana_upper):
        if dia in jornada_tlp:
            row['tlp'+dia] = dias_semana[i]  # Atribui o dia da semana
            pos = jornada_tlp.find(dia)  # Localiza a posiçAo do dia em jornada_tlp para criaçAo de uma substring 'SEG 04:00 QUA 08:00' > 'QUA 08:00'
            jornada_match = re.search(r'\d{2}:\d{2}', jornada_tlp[pos:])  # Localiza a primeira ocorrência de um horário no formato 'HH:MM' após o dia
            if jornada_match:  # Atribui a jornada quando encontrada. Erro já localizado anteriormente
                row['tlp'+dias_semana[i]] = jornada_match.group()
            pos2 = jornada_tlp[pos:].find(':')  # Localiza a posiçAo do primeiro horário a partir de 'pos'
            pos3 = jornada_tlp[pos+pos2+1:].find(':')  # Localiza o segundo horário a partir de 'pos'
            if pos3 == 5:  # Verifica se a distância entre ':' do primeiro e segundo horário é de 5 caracteres '08:[00 01]:00' significando o horário do intervalo
                intervalo_match = re.search(r'(\d{2}:\d{2}) (\d{2}:\d{2})', jornada_tlp[pos:])  # Localiza o intervalo e atribui a coluna
                row['tlpi'+dias_semana[i]] = intervalo_match.group(2)
            else:
                row['tlpi'+dias_semana[i]] = '00:00'
    row['jornada_tlp'] = jornada_tlp

    # CALCULA AS JORNADAS SEMANAIS LEVANDO EM CONSIDERAÇAO OS INTERVALOS
    for day in dias_semana:  # itera pelos dias da semana
        if len(row['tlp'+day]) > 0:  # verifica se o dia tem jornada
            row['tlp'+day.upper()] = row['tlp'+day]  # Substitui 'Seg Ter Qua' pelos horários calculados que serão substituidos em seguida pela jornada encontrada
            row['tlpji0'] = time_to_str((str_to_time(row['tlpji0']))+(str_to_time(row['tlp'+day])))  # Soma as jornadas da semana sem considerar o intervalo
            if row['tlpi'+day] == '00:15':
                row['tlpji15'] = time_to_str((str_to_time(row['tlpji15']))+(str_to_time(row['tlpi'+day])))  # Soma intervalos de 15 minutos
            elif row['tlpi'+day] != '':
                row['tlpji60'] = time_to_str((str_to_time(row['tlpji60']))+(str_to_time(row['tlpi'+day])))  # Soma qualquer outro intervalo que nao 15 minutos
    row['tlpji1'] = time_to_str((str_to_time(row['tlpji15']))+(str_to_time(row['tlpji60']))+(str_to_time(row['tlpji0'])))  # Soma todas as jornadas e intervalos
    row['tlpji15'] = time_to_str((str_to_time(row['tlpji15']))+(str_to_time(row['tlpji0'])))  # Soma jornada + intervalo de 15 minutos
    row['tlpji60'] = time_to_str((str_to_time(row['tlpji60']))+(str_to_time(row['tlpji0'])))  # Soma jornada + qualquer outro intervalo que nao 15 minutos

    if row['NU_CARGA_HORARIA'] == '00:00':  # A jornada mensal tlp padrão já é 00:00
        return row

    # COMPARA AS JORNADAS CALCULADAS COM A JORNADA DA TLP E UTILIZA A PRIMEIRA JORNADA ENCONTRADA, ADICIONANDO OS INTERVALOS AS JORNADAS DE CADA DIA DA SEMANA SE ELAS FIZEREM PARTE
    if row['tlpji0'] == jornada_semanal:  # Compara apenas os dois primeiros dígitos da jornada, desconsiderando diferenças de minutos na jornada pois o TA nao contém horários quebrados
        row['jornada_usada_tlp'] = 'tlpji0'
        # ERROS: Ao encontrar a jornada TLP correta para o funcionario que trabalha em multiplas unidades, muda o espelho de ponto para a jornada encontrada
        if 'TLP: JORNADA MULTIPLAS UNIDADES' in row['erros']:
            row['erros'] = re.sub('TLP: JORNADA MULTIPLAS UNIDADES', '', row['erros'])
            row['horarios'] = row['jornada_tlp']
    elif row['tlpji15'] == jornada_semanal:
        row['jornada_usada_tlp'] = 'tlpji15'
        for day in dias_semana:
            if row['tlpi'+day] == '00:15':
                row['tlp'+day] = time_to_str((str_to_time(row['tlp'+day]))+(str_to_time(row['tlpi'+day])))
        if 'TLP: JORNADA MULTIPLAS UNIDADES' in row['erros']:
            row['erros'] = re.sub('TLP: JORNADA MULTIPLAS UNIDADES', '', row['erros'])
            row['horarios'] = row['jornada_tlp']
    elif row['tlpji60'] == jornada_semanal:
        row['jornada_usada_tlp'] = 'tlpji60'
        for day in dias_semana:
            if len(row['tlpi'+day]) > 0 and row['tlpi'+day] != '00:15':
                row['tlp'+day] = time_to_str((str_to_time(row['tlp'+day]))+(str_to_time(row['tlpi'+day])))
        if 'TLP: JORNADA MULTIPLAS UNIDADES' in row['erros']:
            row['erros'] = re.sub('TLP: JORNADA MULTIPLAS UNIDADES', '', row['erros'])
            row['horarios'] = row['jornada_tlp']
    elif row['tlpji1'] == jornada_semanal:
        row['jornada_usada_tlp'] = 'tlpji1'
        for day in dias_semana:
            if len(row['tlpi'+day]) > 0:
                row['tlp'+day] = time_to_str((str_to_time(row['tlp'+day]))+(str_to_time(row['tlpi'+day])))
        if 'TLP: JORNADA MULTIPLAS UNIDADES' in row['erros']:
            row['erros'] = re.sub('TLP: JORNADA MULTIPLAS UNIDADES', '', row['erros'])
            row['horarios'] = row['jornada_tlp']
    else:
        row['erros'] += ' |TLP_ESPELHO: SEM JORNADA'

    # CALCULA A JORNADA MENSAL BASEADA NA QUANTIDADE DE DIAS UTEIS PARA CADA DIA DA SEMANA
    for i, dia in enumerate(dias_semana):  # Itera a lista de dias da semana
        if row['TIPO_UNIDADE'] == 'AMA' or row['TIPO_UNIDADE'] == 'HD_CONSULTA':  # Não considera feriados para AMA e HD_Penha
            if len(row['tlp'+dia]) > 0:  # Verifica se o dia faz parte da jornada do colaborador
                row['jornada_mensal_tlp'] = time_to_str((str_to_time(row['jornada_mensal_tlp']))+((str_to_time(row['tlp'+dia]))*dias_totais_semana[i]))
        else:
            if len(row['tlp'+dia]) > 0:
                row['jornada_mensal_tlp'] = time_to_str((str_to_time(row['jornada_mensal_tlp']))+((str_to_time(row['tlp'+dia]))*dias_uteis_semana[i]))
    
    # CONVERTE A JORNADA DE SABADO 1 VEZ POR MÊS DE VOLTA PARA O VALOR ORIGINAL
    if jornada_periodica == True:
        for i, jrow in tlp_jornada_nao_semanal.iterrows():
            # if jrow['nome'] == row['NM_PROFISSIONAL']:
            row['tlp'+jrow['dia_semana']] = jrow['jornada']
            row['tlpi'+jrow['dia_semana']] = jrow['intervalo']

    return row


### PROCESSAMENTO

# FUNÇÕES APPLY
tlp = tlp.apply(processa_jornada_tlp, axis=1) 

# ERROS: SE A JORNADA MULTIPLA NAO CAUSOU OUTRO ERRO, DESCONSIDERA O ERRO (DEVE SER EXECUTADO APÓS AS FUNÇÕES APPLY)
tlp.loc[tlp['erros'] == 'TLP: JORNADA MULTIPLAS UNIDADES', 'erros'] = ''

# ERROS:
lancamentos_jornada_tlp = pd.DataFrame(list(set(lancamentos_jornada_tlp.split())), columns=['marcacoes'])  # Cria um dataframe com todos os valores únicos de marcaçAo
lancamentos_jornada_tlp = lancamentos_jornada_tlp.sort_values(by=['marcacoes'])
lancamentos_jornada_tlp.to_excel('log_003_marcacoes_unicas.xlsx', index=False)

### FORMATAÇAO FINAL, EXPORTAÇAO

# Reordena as colunas de acordo com a ordem original
tlp = tlp[original_columns]

tlp.to_excel('log_004_tlp_conferencia.xlsx', index=False)

tlp = tlp.drop([
    'jornada_tlp',
    'tlpDOM', 'tlpSEG', 'tlpTER', 'tlpQUA', 'tlpQUI', 'tlpSEX', 'tlpSAB',
    'tlpiDom', 'tlpiSeg', 'tlpiTer', 'tlpiQua', 'tlpiQui', 'tlpiSex', 'tlpiSab', 
    'tlpji0', 'tlpji15', 'tlpji60', 'tlpji1', 
    'jornada_usada_tlp'], axis=1).reset_index(drop=True)

with open("../tlp.pickle", "wb") as f:
    pickle.dump(tlp, f)

tlp.to_excel('log_005_tlp_jornada_semanal.xlsx', index=False)