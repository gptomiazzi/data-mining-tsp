import random
import geopy.distance
import googlemaps
import networkx as nx
import matplotlib.pyplot as plt
import string
import psycopg2
from psycopg2 import sql
from itertools import permutations

# Definindo os limites aproximados de Cascavel, Paraná, Brasil
# Os valores foram obtidos a partir da análise do perímetro urbano da cidade
top_left = (-24.9358, -53.5277)  # Coordenadas noroeste
bottom_right = (-25.0512, -53.3870)  # Coordenadas sudeste

# Inicializando a API do Google Maps
gmaps = googlemaps.Client(key='AIzaSyBuVDyuAvCFMP1lvy7mK18YK1NHlOTEX4c')

# Conectar ao banco de dados PostgreSQL
conn = psycopg2.connect(
    dbname='data-mining',
    user='postgres',
    password='123456',
    host='localhost',
    port='5432'
)
cursor = conn.cursor()

# Criar tabela para armazenar as coordenadas
cursor.execute('''
    CREATE TABLE IF NOT EXISTS coordenadas (
        id SERIAL PRIMARY KEY,
        latitude DOUBLE PRECISION NOT NULL,
        longitude DOUBLE PRECISION NOT NULL
    )
''')
conn.commit()

def gerar_coordenadas_aleatorias(n=1):
    coordenadas = []
    for _ in range(n):
        latitude = random.uniform(bottom_right[0], top_left[0])
        longitude = random.uniform(top_left[1], bottom_right[1])
        coordenadas.append((latitude, longitude))
    return coordenadas

# Função para salvar coordenadas no banco de dados
def salvar_coordenadas(coordenadas):
    for coord in coordenadas:
        cursor.execute(
            'INSERT INTO coordenadas (latitude, longitude) VALUES (%s, %s)',
            (coord[0], coord[1])
        )
    conn.commit()

# Função para obter coordenadas do banco de dados
def obter_coordenadas():
    cursor.execute('SELECT latitude, longitude FROM coordenadas')
    return cursor.fetchall()

# Função para calcular a distância entre duas coordenadas usando a API do Google Maps
# Limitando o modo de transporte para terrestre (driving)
def calcular_distancia_google_maps(coord_origem, coord_destino):
    origem = f"{coord_origem[0]},{coord_origem[1]}"
    destino = f"{coord_destino[0]},{coord_destino[1]}"
    resultado = gmaps.distance_matrix(origem, destino, mode="driving")
    distancia = resultado["rows"][0]["elements"][0]["distance"]["value"]  # Distância em metros
    distancia = round(distancia / 1000)  # Converter para quilômetros e arredondar
    return distancia

# Menu de opções
def menu():
    while True:
        print("\nEscolha uma opção:")
        print("1 - Gerar gráfico com a menor rota (TSP)")
        print("2 - Listar registros do banco")
        print("3 - Gerar mais localizações")
        print("4 - Sair")
        opcao = input("Opção: ")

        if opcao == "1":
            gerar_grafo_tsp()
        elif opcao == "2":
            listar_registros()
        elif opcao == "3":
            gerar_mais_localizacoes()
        elif opcao == "4":
            break
        else:
            print("Opção inválida. Tente novamente.")

# Função para gerar o grafo resolvendo o Travelling Salesman Problem
def gerar_grafo_tsp():
    coordenadas = obter_coordenadas()
    if len(coordenadas) < 2:
        print("É necessário ter pelo menos duas coordenadas para gerar a rota.")
        return

    grafo = nx.Graph()
    labels_nos = list(string.ascii_uppercase[:len(coordenadas)])
    for idx, coordenada in enumerate(coordenadas):
        grafo.add_node(labels_nos[idx], pos=coordenada, color='green' if idx == 0 else 'red' if idx == len(coordenadas) - 1 else 'skyblue')

    # Calcular distâncias entre todos os pontos e armazenar em um dicionário
    distancias = {}
    for i in range(len(coordenadas)):
        for j in range(i + 1, len(coordenadas)):
            distancia = calcular_distancia_google_maps(coordenadas[i], coordenadas[j])
            distancias[(i, j)] = distancia
            distancias[(j, i)] = distancia

    # Travelling Salesman Problem: encontrar a menor rota
    n = len(coordenadas)
    indices = list(range(1, n - 1))  # Excluindo o primeiro e o último nó
    menor_distancia = float('inf')
    melhor_percurso = None

    # Gerar todas as permutações possíveis entre os pontos intermediários
    todas_rotas = []
    for permutacao in permutations(indices):
        percurso = [0] + list(permutacao) + [n - 1]
        distancia_total = 0
        for k in range(len(percurso) - 1):
            distancia_total += distancias[(percurso[k], percurso[k + 1])]
        todas_rotas.append((percurso, distancia_total))
        if distancia_total < menor_distancia:
            menor_distancia = distancia_total
            melhor_percurso = percurso

    # Adicionar todas as arestas ao grafo
    for i in range(len(coordenadas)):
        for j in range(i + 1, len(coordenadas)):
            distancia = distancias[(i, j)]
            grafo.add_edge(labels_nos[i], labels_nos[j], weight=distancia)

    # Plotar o grafo original com a rota mais curta
    pos = nx.spring_layout(grafo, weight='weight', iterations=100)
    colors = [grafo.nodes[node]['color'] for node in grafo.nodes()]
    plt.figure(figsize=(10, 8))
    nx.draw(grafo, pos, with_labels=True, node_size=400, node_color=colors, font_size=10)
    rota_otima = [(labels_nos[melhor_percurso[i]], labels_nos[melhor_percurso[i + 1]]) for i in range(len(melhor_percurso) - 1)]
    nx.draw_networkx_edges(grafo, pos, edgelist=rota_otima, edge_color='r', width=2, alpha=0.8, label='Rota Ótima', arrowstyle='->', arrows=True)
    nx.draw_networkx_edge_labels(grafo, pos, edge_labels={edge: f"{distancias[(labels_nos.index(edge[0]), labels_nos.index(edge[1]))]}KM" for edge in rota_otima}, font_size=8, bbox=dict(facecolor='white', edgecolor='none', alpha=0.7), label_pos=0.6)
    plt.title("Gráfico com a Rota Mais Curta (Vermelha)")
    plt.text(0.95, 0.05, f"Distância Total do percurso: {menor_distancia} KM", ha='right', va='center', transform=plt.gca().transAxes, fontsize=10, bbox=dict(facecolor='white', alpha=0.5))
    plt.show()

    # Gerar gráficos para todas as rotas possíveis
    color_map = plt.cm.get_cmap('tab20', len(todas_rotas))
    for idx, (rota, distancia_total) in enumerate(todas_rotas):
        plt.figure(figsize=(10, 8))
        nx.draw(grafo, pos, with_labels=True, node_size=400, node_color=colors, font_size=10)
        edges_rota = [(labels_nos[rota[i]], labels_nos[rota[i + 1]]) for i in range(len(rota) - 1)]
        nx.draw_networkx_edges(grafo, pos, edgelist=edges_rota, edge_color=[color_map(idx)], width=2, alpha=0.8)
        nx.draw_networkx_edge_labels(grafo, pos, edge_labels={edge: f"{distancias[(labels_nos.index(edge[0]), labels_nos.index(edge[1]))]}KM" for edge in edges_rota}, font_size=8, bbox=dict(facecolor='white', edgecolor='none', alpha=0.7), label_pos=0.6)
        plt.title(f"Gráfico da Rota {idx + 1} (Distância Total: {distancia_total} KM)")
        plt.text(0.95, 0.05, f"Distância Total do percurso: {distancia_total} KM", ha='right', va='center', transform=plt.gca().transAxes, fontsize=10, bbox=dict(facecolor='white', alpha=0.5))
    plt.show()

# Função para listar registros do banco de dados
def listar_registros():
    coordenadas = obter_coordenadas()
    for idx, coordenada in enumerate(coordenadas, start=1):
        print(f"Coordenada {idx}: Latitude {coordenada[0]}, Longitude {coordenada[1]}")

# Função para gerar mais localizações e salvar no banco de dados
def gerar_mais_localizacoes():
    n = int(input("Quantas novas coordenadas deseja gerar? "))
    novas_coordenadas = gerar_coordenadas_aleatorias(n)
    salvar_coordenadas(novas_coordenadas)
    print(f"{n} novas coordenadas foram salvas no banco de dados.")

# Executar o menu
menu()

# Fechar a conexão com o banco de dados
cursor.close()
conn.close()
