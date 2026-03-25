"""
NCM (Nomenclatura Comum do Mercosul) code registry.

Contains a frozen set of valid 8-digit NCM codes from the official TIPI
(Tabela de Incidencia do Imposto sobre Produtos Industrializados) maintained
by the Brazilian Federal Revenue (Receita Federal do Brasil).

NCM codes follow the Harmonized System (HS) structure:
  - Digits 1-2: Chapter
  - Digits 3-4: Position
  - Digits 5-6: Sub-position (HS level)
  - Digits 7-8: National sub-item (Mercosul level)

Reference: Decreto 11.158/2022 (TIPI) and subsequent updates.
"""

VALID_NCM_CODES: frozenset[str] = frozenset({
    # ──────────────────────────────────────────────────────────────────────
    # Chapter 01 — Live animals
    # ──────────────────────────────────────────────────────────────────────
    "01012100",  # Cavalos puro-sangue de raça
    "01022110",  # Bovinos reprodutores de raça pura
    "01041000",  # Ovinos vivos
    "01051110",  # Galos e galinhas, peso <= 185g
    "01061900",  # Outros mamiferos vivos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 02 — Meat and edible offal
    # ──────────────────────────────────────────────────────────────────────
    "02011000",  # Carcaças e meias-carcaças de bovino, frescas/refrigeradas
    "02012010",  # Quartos dianteiros de bovino, nao desossados
    "02012020",  # Quartos traseiros de bovino, nao desossados
    "02013000",  # Carnes desossadas de bovino, frescas/refrigeradas
    "02021000",  # Carcaças e meias-carcaças de bovino, congeladas
    "02023000",  # Carnes desossadas de bovino, congeladas
    "02031100",  # Carcaças e meias-carcaças de suino, frescas/refrigeradas
    "02031200",  # Pernis, pas e pedacos de suino, nao desossados
    "02032100",  # Carcaças e meias-carcaças de suino, congeladas
    "02071100",  # Carnes de galos/galinhas, nao cortadas em pedacos, frescas
    "02071200",  # Carnes de galos/galinhas, nao cortadas em pedacos, congeladas
    "02071400",  # Pedacos e miudezas de galos/galinhas, congelados

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 03 — Fish, crustaceans, molluscs
    # ──────────────────────────────────────────────────────────────────────
    "03021100",  # Trutas frescas/refrigeradas
    "03023100",  # Atuns-albacora frescos/refrigerados
    "03034100",  # Atuns-albacora congelados
    "03034200",  # Atuns-de-barbatana-amarela congelados
    "03036100",  # Espadarte congelado
    "03061710",  # Camaroes congelados
    "03074200",  # Lulas e potas, vivas/frescas/refrigeradas
    "03089000",  # Outros invertebrados aquaticos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 04 — Dairy, eggs, honey
    # ──────────────────────────────────────────────────────────────────────
    "04011010",  # Leite UHT, teor de gordura <= 1%
    "04012110",  # Leite UHT, teor de gordura 1-6%
    "04012190",  # Outros leites nao concentrados, 1-6% gordura
    "04014000",  # Leite e creme de leite, gordura > 6%
    "04015010",  # Leite e creme de leite, gordura > 6%, acondic. <= 2kg
    "04021010",  # Leite em po, gordura <= 1,5%
    "04022110",  # Leite em po, sem adicao de acucar, gordura > 1,5%
    "04031000",  # Iogurte
    "04041000",  # Soro de leite
    "04051000",  # Manteiga
    "04061000",  # Queijo fresco (nao curado)
    "04069010",  # Mussarela
    "04070011",  # Ovos de galinha, fecundados
    "04070019",  # Outros ovos de ave, fecundados
    "04090000",  # Mel natural

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 05 — Other animal products
    # ──────────────────────────────────────────────────────────────────────
    "05040011",  # Tripas de bovino
    "05111000",  # Semen de bovino

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 06 — Live trees and plants
    # ──────────────────────────────────────────────────────────────────────
    "06024000",  # Roseiras, enxertadas ou nao

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 07 — Edible vegetables
    # ──────────────────────────────────────────────────────────────────────
    "07019000",  # Batatas frescas/refrigeradas
    "07020000",  # Tomates frescos/refrigerados
    "07031019",  # Cebolas frescas/refrigeradas
    "07041000",  # Couve-flor e brocolis
    "07061000",  # Cenouras e nabos
    "07081000",  # Ervilhas frescas
    "07089100",  # Alcachofras
    "07096000",  # Pimentoes (Capsicum/Pimenta)
    "07099100",  # Alcachofras
    "07101000",  # Batatas congeladas
    "07133319",  # Feijao preto
    "07133399",  # Outros feijoes

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 08 — Edible fruits and nuts
    # ──────────────────────────────────────────────────────────────────────
    "08030000",  # Bananas frescas ou secas
    "08051000",  # Laranjas frescas/secas
    "08052100",  # Mandarinas/tangerinas frescas/secas
    "08061000",  # Uvas frescas
    "08071100",  # Melancias
    "08081000",  # Macas frescas
    "08083000",  # Peras frescas
    "08109010",  # Castanha de caju fresca
    "08109020",  # Manga fresca

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 09 — Coffee, tea, spices
    # ──────────────────────────────────────────────────────────────────────
    "09011110",  # Cafe nao torrado, nao descafeinado, em grao
    "09011190",  # Outro cafe nao torrado, nao descafeinado
    "09012100",  # Cafe torrado nao descafeinado
    "09024000",  # Cha preto fermentado
    "09042110",  # Pimenta seca, nao triturada

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 10 — Cereals
    # ──────────────────────────────────────────────────────────────────────
    "10011100",  # Trigo duro para semeadura
    "10019900",  # Outros trigos e misturas
    "10051000",  # Milho para semeadura
    "10059010",  # Milho em grao, exceto para semeadura
    "10059090",  # Outros milhos
    "10061011",  # Arroz com casca (paddy) para semeadura
    "10063011",  # Arroz semibranqueado, parboilizado
    "10063021",  # Arroz semibranqueado, nao parboilizado

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 11 — Milling products, malt, starch
    # ──────────────────────────────────────────────────────────────────────
    "11010010",  # Farinha de trigo
    "11022000",  # Farinha de milho
    "11071010",  # Malte nao torrado, inteiro/partido

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 12 — Oil seeds
    # ──────────────────────────────────────────────────────────────────────
    "12010010",  # Soja para semeadura
    "12019000",  # Soja, exceto para semeadura
    "12024200",  # Amendoim descascado
    "12074010",  # Sementes de gergelim

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 13-14 — Gums, vegetable plaiting materials
    # ──────────────────────────────────────────────────────────────────────
    "13021100",  # Suco de opium
    "14049090",  # Outros produtos vegetais

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 15 — Fats and oils
    # ──────────────────────────────────────────────────────────────────────
    "15079011",  # Oleo de soja, refinado, em recipientes < 5L
    "15079019",  # Oleo de soja, refinado, outros
    "15091000",  # Azeite de oliva virgem
    "15099000",  # Outros azeites de oliva
    "15121110",  # Oleo de girassol, bruto
    "15131100",  # Oleo de coco bruto
    "15171000",  # Margarina

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 16 — Preparations of meat/fish
    # ──────────────────────────────────────────────────────────────────────
    "16010000",  # Enchidos e produtos semelhantes de carne
    "16024100",  # Preparacoes de pernis de suino
    "16025000",  # Preparacoes de carne bovina

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 17 — Sugars and confectionery
    # ──────────────────────────────────────────────────────────────────────
    "17011400",  # Outros acucares de cana
    "17019900",  # Outros acucares, incluindo invertido
    "17049010",  # Chocolate branco

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 18 — Cocoa and preparations
    # ──────────────────────────────────────────────────────────────────────
    "18010000",  # Cacau inteiro, quebrado, cru/torrado
    "18063100",  # Chocolate recheado
    "18069000",  # Outros chocolates e preparacoes com cacau

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 19 — Preparations of cereals, pastry
    # ──────────────────────────────────────────────────────────────────────
    "19011010",  # Preparacoes para alimentacao de criancas
    "19021100",  # Massas nao cozidas, contendo ovos
    "19021900",  # Outras massas nao cozidas
    "19053100",  # Biscoitos doces (cookies)
    "19059020",  # Bolos industrializados

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 20 — Preparations of vegetables/fruits
    # ──────────────────────────────────────────────────────────────────────
    "20091100",  # Suco de laranja, congelado
    "20091200",  # Suco de laranja, nao congelado, Brix <= 20
    "20098900",  # Outros sucos de fruta

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 21 — Miscellaneous food preparations
    # ──────────────────────────────────────────────────────────────────────
    "21011110",  # Cafe soluvel
    "21069090",  # Outras preparacoes alimenticias

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 22 — Beverages, spirits, vinegar
    # ──────────────────────────────────────────────────────────────────────
    "22011000",  # Aguas minerais e gaseificadas
    "22019000",  # Outras aguas nao adocadas
    "22021000",  # Aguas com adicao de acucar
    "22030000",  # Cervejas de malte
    "22041000",  # Vinhos espumantes
    "22042100",  # Vinhos em recipientes <= 2L
    "22071000",  # Alcool etilico >= 80%
    "22084000",  # Rum e tafia
    "22089000",  # Outros destilados

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 23 — Residues from food industries, animal feed
    # ──────────────────────────────────────────────────────────────────────
    "23040010",  # Farinhas e pellets de soja
    "23099010",  # Preparacoes para caes ou gatos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 24 — Tobacco
    # ──────────────────────────────────────────────────────────────────────
    "24012030",  # Tabaco nao manufaturado, parcialm. destalado
    "24022000",  # Cigarros contendo tabaco

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 25 — Salt, sulphur, earths, stone
    # ──────────────────────────────────────────────────────────────────────
    "25010011",  # Sal marinho
    "25010019",  # Outro sal (exceto para mesa)
    "25051000",  # Areias siliciosas
    "25232900",  # Cimento Portland, outros
    "25309000",  # Outros minerais

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 26 — Ores, slag, ash
    # ──────────────────────────────────────────────────────────────────────
    "26011100",  # Minerio de ferro nao aglomerado

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 27 — Mineral fuels, oils
    # ──────────────────────────────────────────────────────────────────────
    "27011200",  # Hulha betuminosa
    "27090010",  # Petroleo bruto
    "27101159",  # Outras gasolinas
    "27101241",  # Oleo diesel B (mistura biodiesel)
    "27101259",  # Outros oleos combustiveis
    "27101921",  # Lubrificantes
    "27111100",  # Gas natural liquefeito
    "27111300",  # Butano liquefeito
    "27112100",  # Gas natural em estado gasoso

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 28 — Inorganic chemicals
    # ──────────────────────────────────────────────────────────────────────
    "28112100",  # Dioxido de carbono (CO2)
    "28151100",  # Hidroxido de sodio (soda caustica) solido
    "28170010",  # Oxido de zinco
    "28362000",  # Carbonato dissodico

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 29 — Organic chemicals
    # ──────────────────────────────────────────────────────────────────────
    "29012100",  # Etileno
    "29012200",  # Propeno
    "29024100",  # O-xileno
    "29051100",  # Metanol (alcool metilico)
    "29053100",  # Etilenoglicol

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 30 — Pharmaceutical products
    # ──────────────────────────────────────────────────────────────────────
    "30021200",  # Antissoros e fracoes do sangue
    "30023000",  # Vacinas para medicina veterinaria
    "30042019",  # Outros medicamentos com antibioticos
    "30043100",  # Medicamentos contendo insulina
    "30043999",  # Outros medicamentos com hormonios
    "30049039",  # Outros medicamentos em doses
    "30049069",  # Outros medicamentos, nao em doses
    "30049099",  # Outros medicamentos para venda a retalho
    "30051010",  # Pensos adesivos (curativos)
    "30059090",  # Outros artigos farmaceuticos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 31 — Fertilizers
    # ──────────────────────────────────────────────────────────────────────
    "31021000",  # Ureia
    "31031100",  # Superfosfatos, >= 35% P2O5
    "31052000",  # Adubos minerais, com N, P e K
    "31059090",  # Outros adubos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 32 — Tanning/dyeing extracts, paints
    # ──────────────────────────────────────────────────────────────────────
    "32089090",  # Outras tintas e vernizes
    "32091000",  # Tintas a base de polimeros acrilicos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 33 — Essential oils, cosmetics
    # ──────────────────────────────────────────────────────────────────────
    "33030010",  # Perfumes
    "33041000",  # Produtos de maquiagem para labios
    "33049100",  # Pos, incluidos compactos
    "33051000",  # Champus (shampoos)
    "33061000",  # Dentifricios

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 34 — Soap, washing preparations
    # ──────────────────────────────────────────────────────────────────────
    "34011190",  # Saboes de toucador
    "34022000",  # Preparacoes tensoativas (detergentes)

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 35-37 — Albumins, glues, photographic
    # ──────────────────────────────────────────────────────────────────────
    "35069190",  # Outros adesivos
    "37024410",  # Filmes fotograficos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 38 — Miscellaneous chemical products
    # ──────────────────────────────────────────────────────────────────────
    "38089199",  # Outros inseticidas
    "38089290",  # Outros fungicidas
    "38089999",  # Outros produtos quimicos diversos
    "38220000",  # Reagentes de diagnostico

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 39 — Plastics and articles thereof
    # ──────────────────────────────────────────────────────────────────────
    "39011010",  # Polietileno, densidade < 0,94, em formas primarias
    "39012019",  # Polietileno, densidade >= 0,94
    "39021000",  # Polipropileno em formas primarias
    "39023000",  # Copolimeros de propileno
    "39031100",  # Poliestireno expansivel
    "39041000",  # PVC nao misturado
    "39069090",  # Outros polimeros acrilicos
    "39076100",  # PET (politereftalato de etileno)
    "39199000",  # Outras chapas auto-adesivas de plastico
    "39231000",  # Caixas, engradados de plastico
    "39232100",  # Sacos de polimeros de etileno
    "39232990",  # Outros sacos de plastico
    "39241000",  # Servicos de mesa de plastico
    "39269090",  # Outros artigos de plastico

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 40 — Rubber and articles thereof
    # ──────────────────────────────────────────────────────────────────────
    "40111000",  # Pneumaticos novos para automoveis
    "40112010",  # Pneumaticos novos para onibus/caminhoes
    "40116100",  # Pneumaticos novos para uso agricola
    "40119200",  # Outros pneumaticos novos
    "40139000",  # Camaras de ar

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 41 — Raw hides, skins, leather
    # ──────────────────────────────────────────────────────────────────────
    "41041100",  # Couros e peles de bovino, plena flor
    "41044100",  # Couros e peles curtidos de bovino, secos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 42-43 — Leather articles, furskins
    # ──────────────────────────────────────────────────────────────────────
    "42021200",  # Malas e maletas com superficie de plastico
    "42023200",  # Carteiras e porta-moedas de plastico/textil
    "43021900",  # Peles curtidas ou acabadas

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 44 — Wood and articles of wood
    # ──────────────────────────────────────────────────────────────────────
    "44011100",  # Lenha em toras
    "44012200",  # Madeira em estilhas de nao-coniferas
    "44039900",  # Outras madeiras em bruto
    "44071100",  # Madeira de pinheiro, serrada
    "44079900",  # Outras madeiras serradas
    "44101100",  # Paineis de particulas de madeira
    "44111200",  # Paineis de fibra MDF, esp. <= 5mm
    "44111300",  # Paineis de fibra MDF, 5mm < esp. <= 9mm
    "44111400",  # Paineis de fibra MDF, esp. > 9mm
    "44123300",  # Compensados com face de nao-coniferas

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 47-48 — Pulp, paper
    # ──────────────────────────────────────────────────────────────────────
    "47032100",  # Pasta quimica de madeira, coniferas, semi-branqueada
    "48010010",  # Papel de jornal em bobinas
    "48025290",  # Outros papeis/cartoes, 40-150 g/m2
    "48030000",  # Papel higienico e semelhantes
    "48041100",  # Kraftliner cru, nao revestido
    "48051100",  # Papel fluting semi-quimico
    "48191000",  # Caixas de papelao ondulado
    "48192000",  # Caixas dobraveis de papelao nao ondulado

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 49 — Printed books, newspapers
    # ──────────────────────────────────────────────────────────────────────
    "49011000",  # Livros, brochuras, impressos
    "49019900",  # Outros livros, folhetos impressos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 50-55 — Textiles (silk through man-made staple fibres)
    # ──────────────────────────────────────────────────────────────────────
    "52010010",  # Algodao nao cardado nem penteado
    "52030000",  # Algodao cardado ou penteado
    "52051100",  # Fios de algodao, >= 85%, simples
    "52082100",  # Tecidos de algodao, branqueados, tela
    "54024600",  # Fios de poliester, parcialmente orientados
    "54077100",  # Tecidos de poliester, >= 85%
    "55032000",  # Fibras de poliester descontinuas

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 56-60 — Wadding, rope, knitted fabrics
    # ──────────────────────────────────────────────────────────────────────
    "56012100",  # Algodao hidrófilo e artigos de algodao
    "60062100",  # Tecidos de malha de algodao

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 61 — Knitted/crocheted clothing
    # ──────────────────────────────────────────────────────────────────────
    "61034200",  # Calcas de algodao, de malha, masculinas
    "61046200",  # Calcas de algodao, de malha, femininas
    "61051000",  # Camisas de malha, masculinas, algodao
    "61061000",  # Camisas de malha, femininas, algodao
    "61091000",  # Camisetas (T-shirts) de malha, algodao
    "61099000",  # Outras camisetas de malha
    "61112000",  # Vestuario para bebes, de algodao, malha
    "61159600",  # Meias de fibras sinteticas

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 62 — Non-knitted clothing
    # ──────────────────────────────────────────────────────────────────────
    "62033200",  # Paletós e blazers de algodao, masculinos
    "62034200",  # Calcas de algodao, masculinas
    "62042200",  # Conjuntos de algodao, femininos
    "62046200",  # Calcas de algodao, femininas
    "62052000",  # Camisas de algodao, masculinas
    "62114200",  # Vestuario feminino de algodao

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 63 — Other made-up textile articles
    # ──────────────────────────────────────────────────────────────────────
    "63021000",  # Roupas de cama, de malha
    "63053300",  # Sacos para embalagem, de polietileno

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 64 — Footwear
    # ──────────────────────────────────────────────────────────────────────
    "64019200",  # Calcados impermeáveis cobrindo tornozelo
    "64021200",  # Calcados de esqui
    "64029990",  # Outros calcados com sola de borracha
    "64041100",  # Calcados para esporte, com sola de borracha
    "64041900",  # Outros calcados com parte superior de textil
    "64052000",  # Outros calcados com parte superior de textil

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 65-67 — Hats, umbrellas, feathers
    # ──────────────────────────────────────────────────────────────────────
    "65050090",  # Outros chapeus e artigos de uso semelhante
    "66019100",  # Guarda-chuvas telescopicos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 68 — Stone, plaster, cement articles
    # ──────────────────────────────────────────────────────────────────────
    "68022100",  # Mármores trabalhados
    "68091100",  # Chapas de gesso nao ornamentadas

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 69 — Ceramic products
    # ──────────────────────────────────────────────────────────────────────
    "69072100",  # Ladrilhos ceramicos, absorcao de agua <= 0,5%
    "69089000",  # Outros ladrilhos e azulejos ceramicos
    "69111000",  # Artigos para mesa de porcelana

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 70 — Glass and glassware
    # ──────────────────────────────────────────────────────────────────────
    "70051000",  # Vidro float, polido, com camada absorvente
    "70099200",  # Espelhos de vidro, emoldurados
    "70109021",  # Garrafas de vidro, capacidade > 0,33L
    "70134200",  # Artigos de vidro para mesa, chumbo >= 24%

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 71 — Precious metals/stones, jewelry
    # ──────────────────────────────────────────────────────────────────────
    "71081300",  # Ouro em outras formas semi-manufaturadas
    "71131100",  # Artigos de joalharia de prata
    "71171100",  # Abotoaduras de metais comuns

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 72 — Iron and steel
    # ──────────────────────────────────────────────────────────────────────
    "72061000",  # Ferro e aco nao-ligado em lingotes
    "72082500",  # Produtos laminados a quente, esp. >= 4,75mm
    "72083900",  # Outros laminados a quente, esp. < 3mm
    "72091600",  # Laminados a frio, 1mm < esp. < 3mm
    "72104900",  # Outros laminados revestidos de zinco
    "72142000",  # Barras de ferro/aco, laminadas a quente
    "72163100",  # Perfis U de ferro/aco, laminados a quente
    "72193200",  # Laminados planos de aco inoxidavel, 3mm-4,75mm

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 73 — Articles of iron/steel
    # ──────────────────────────────────────────────────────────────────────
    "73021000",  # Trilhos de ferro/aco
    "73042900",  # Outros tubos de revestimento de aco
    "73063000",  # Outros tubos soldados de ferro/aco
    "73089090",  # Outras construcoes de ferro/aco
    "73110000",  # Recipientes de ferro/aco para gas comprimido
    "73141400",  # Telas metalicas de aco inoxidavel
    "73181500",  # Outros parafusos e pinos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 74-75 — Copper, nickel
    # ──────────────────────────────────────────────────────────────────────
    "74031100",  # Catodos de cobre refinado
    "74081100",  # Fios de cobre refinado

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 76 — Aluminium and articles thereof
    # ──────────────────────────────────────────────────────────────────────
    "76011000",  # Aluminio nao ligado em formas brutas
    "76061200",  # Chapas de liga de aluminio, esp. > 0,2mm
    "76071110",  # Folhas de aluminio, laminadas, esp. < 0,2mm
    "76151000",  # Artigos de mesa de aluminio
    "76161000",  # Tachas, pregos de aluminio

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 78-83 — Lead, zinc, tin, other base metals
    # ──────────────────────────────────────────────────────────────────────
    "79011100",  # Zinco nao ligado, >= 99,99%
    "83024100",  # Guarnicoes de metais comuns para moveis
    "83062100",  # Estatuetas de metais comuns

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 84 — Nuclear reactors, boilers, machinery
    # ──────────────────────────────────────────────────────────────────────
    "84051000",  # Geradores de gas
    "84099190",  # Outras partes para motores de pistao
    "84133010",  # Bombas de combustivel para motores
    "84137010",  # Bombas centrifugas
    "84186990",  # Outros equipamentos de refrigeracao
    "84189900",  # Partes de refrigeradores/congeladores
    "84211100",  # Desnatadeiras centrifugas
    "84212300",  # Filtros de oleo para motores
    "84221100",  # Maquinas de lavar louca domesticas
    "84501100",  # Maquinas de lavar roupa, automaticas, <= 10kg
    "84501200",  # Outras maquinas de lavar roupa, <= 10kg
    "84713012",  # Computadores portateis (notebooks) <= 10 kg
    "84713019",  # Outros computadores portateis
    "84714100",  # Outras maquinas de processamento de dados
    "84714900",  # Outros computadores apresentados em sistemas
    "84715010",  # Unidades de processamento digitais
    "84716052",  # Teclados
    "84716053",  # Dispositivos apontadores (mouse)
    "84717012",  # Unidades de discos magneticos (HDD)
    "84717019",  # Outras unidades de memoria
    "84718000",  # Outras unidades de maquinas de processamento
    "84733020",  # Partes de maquinas de processamento de dados
    "84798999",  # Outras maquinas e aparelhos mecanicos

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 85 — Electrical machinery and equipment
    # ──────────────────────────────────────────────────────────────────────
    "85015110",  # Motores eletricos, CA, polifasicos, <= 750W
    "85030090",  # Partes de motores/geradores eletricos
    "85044090",  # Outros conversores estaticos
    "85171200",  # Telefones celulares e redes sem fio
    "85176200",  # Aparelhos para recepcao/conversao de voz/imagem/dados
    "85177000",  # Partes de aparelhos telefonicos
    "85182100",  # Alto-falante unico montado
    "85232110",  # Cartoes de memoria (fitas magneticas)
    "85234910",  # Discos opticos para gravacao
    "85238000",  # Outros suportes para gravacao
    "85258019",  # Outras cameras de televisao
    "85285100",  # Monitores com tubo de raios catodicos
    "85285210",  # Monitores LCD
    "85286200",  # Projetores
    "85340000",  # Circuitos impressos
    "85411000",  # Diodos (exceto fotodiodos/LED)
    "85421000",  # Cartoes com circuito integrado (smart cards)
    "85423100",  # Processadores e controladores
    "85423200",  # Memorias
    "85423900",  # Outros circuitos integrados
    "85437099",  # Outros aparelhos eletricos
    "85444200",  # Outros condutores eletricos, <= 1000V, com conectores

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 86 — Railway/tramway stock
    # ──────────────────────────────────────────────────────────────────────
    "86071100",  # Bogies motores de locomotivas

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 87 — Vehicles (not railway)
    # ──────────────────────────────────────────────────────────────────────
    "87011000",  # Tratores de eixo simples
    "87019490",  # Outros tratores, potencia > 130cv
    "87021000",  # Veiculos de transporte >= 10 pessoas, diesel
    "87032100",  # Automoveis, cilindrada <= 1000cm3
    "87032310",  # Automoveis, 1500-3000cm3
    "87033100",  # Automoveis diesel, cilindrada <= 1500cm3
    "87041010",  # Dumpers para uso fora de rodovias
    "87042100",  # Veiculos de carga, diesel, PBT <= 5t
    "87042290",  # Outros veiculos de carga, diesel, 5-20t
    "87060010",  # Chassis com motor para veiculos de passageiros
    "87071000",  # Carrocerias para automoveis
    "87082999",  # Outras partes de carrocerias
    "87083090",  # Outros freios e partes
    "87084090",  # Outras caixas de marchas
    "87085099",  # Outros eixos e partes
    "87089990",  # Outras partes e acessorios de veiculos
    "87112000",  # Motocicletas 50-250cm3
    "87141000",  # Partes de motocicletas

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 88 — Aircraft, spacecraft
    # ──────────────────────────────────────────────────────────────────────
    "88024000",  # Avioes, peso vazio > 15000kg
    "88033000",  # Partes de avioes/helicopteros

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 89 — Ships, boats
    # ──────────────────────────────────────────────────────────────────────
    "89039200",  # Barcos a motor (exceto popa), comprimento > 7,5m
    "89052000",  # Plataformas de perfuracao flutuantes

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 90 — Optical, measuring, medical instruments
    # ──────────────────────────────────────────────────────────────────────
    "90011000",  # Fibras opticas
    "90049000",  # Outros oculos
    "90181200",  # Aparelhos de ultrasonografia
    "90181990",  # Outros aparelhos de eletrodiagnostico
    "90183100",  # Seringas
    "90183210",  # Agulhas tubulares de metal
    "90183929",  # Outros cateteres
    "90189099",  # Outros instrumentos medicos/cirurgicos
    "90191010",  # Aparelhos de mecanoterapia
    "90211000",  # Aparelhos ortopedicos
    "90221200",  # Aparelhos de tomografia computadorizada
    "90221400",  # Outros aparelhos de raios X
    "90268000",  # Outros instrumentos de medida de liquidos/gases
    "90318099",  # Outros instrumentos de medida

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 91 — Clocks and watches
    # ──────────────────────────────────────────────────────────────────────
    "91021100",  # Relogios de pulso, com visor mecânico
    "91022900",  # Outros relogios de pulso

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 92 — Musical instruments
    # ──────────────────────────────────────────────────────────────────────
    "92011000",  # Pianos verticais
    "92029000",  # Outros instrumentos de cordas

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 93 — Arms and ammunition
    # ──────────────────────────────────────────────────────────────────────
    "93020000",  # Revolveres e pistolas
    "93063000",  # Outros cartuchos e suas partes

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 94 — Furniture, bedding, lighting
    # ──────────────────────────────────────────────────────────────────────
    "94011000",  # Assentos para aeronaves
    "94012000",  # Assentos para veiculos automotores
    "94017900",  # Outros assentos com armacao de metal
    "94032000",  # Outros moveis de metal
    "94034000",  # Moveis de cozinha de madeira
    "94035000",  # Moveis de quarto de madeira
    "94036000",  # Outros moveis de madeira
    "94042100",  # Colchoes de borracha alveolar
    "94051000",  # Lustres e outros aparelhos de iluminacao

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 95 — Toys, games, sports
    # ──────────────────────────────────────────────────────────────────────
    "95030021",  # Triciclos, patinetes, carros de pedais
    "95030031",  # Outros brinquedos, com motor
    "95030099",  # Outros brinquedos
    "95042000",  # Bilhares e acessorios
    "95066200",  # Bolas inflaveis

    # ──────────────────────────────────────────────────────────────────────
    # Chapter 96 — Miscellaneous manufactured articles
    # ──────────────────────────────────────────────────────────────────────
    "96032100",  # Escovas de dentes
    "96081000",  # Canetas esferograficas
    "96089200",  # Canetas com ponta de feltro
    "96190000",  # Absorventes e tampos higienicos
})


def is_valid_ncm(code: str) -> bool:
    """Check if an NCM code exists in the TIPI table.

    Args:
        code: 8-digit NCM code string (e.g. "84713012").

    Returns:
        True if the code is present in the curated set of valid NCM codes.
    """
    return code in VALID_NCM_CODES


NCM_DESCRIPTIONS: dict[str, str] = {
    "01012100": "Cavalos puro-sangue de raça",
    "01022110": "Bovinos reprodutores de raça pura",
    "01041000": "Ovinos vivos",
    "01051110": "Galos e galinhas, peso <= 185g",
    "01061900": "Outros mamiferos vivos",
    "02011000": "Carcaças e meias-carcaças de bovino, frescas/refrigeradas",
    "02012010": "Quartos dianteiros de bovino, nao desossados",
    "02012020": "Quartos traseiros de bovino, nao desossados",
    "02013000": "Carnes desossadas de bovino, frescas/refrigeradas",
    "02021000": "Carcaças e meias-carcaças de bovino, congeladas",
    "02023000": "Carnes desossadas de bovino, congeladas",
    "02031100": "Carcaças e meias-carcaças de suino, frescas/refrigeradas",
    "02031200": "Pernis, pas e pedacos de suino, nao desossados",
    "02032100": "Carcaças e meias-carcaças de suino, congeladas",
    "02071100": "Carnes de galos/galinhas, nao cortadas em pedacos, frescas",
    "02071200": "Carnes de galos/galinhas, nao cortadas em pedacos, congeladas",
    "02071400": "Pedacos e miudezas de galos/galinhas, congelados",
    "03021100": "Trutas frescas/refrigeradas",
    "03023100": "Atuns-albacora frescos/refrigerados",
    "03034100": "Atuns-albacora congelados",
    "03034200": "Atuns-de-barbatana-amarela congelados",
    "03036100": "Espadarte congelado",
    "03061710": "Camaroes congelados",
    "03074200": "Lulas e potas, vivas/frescas/refrigeradas",
    "03089000": "Outros invertebrados aquaticos",
    "04011010": "Leite UHT, teor de gordura <= 1%",
    "04012110": "Leite UHT, teor de gordura 1-6%",
    "04012190": "Outros leites nao concentrados, 1-6% gordura",
    "04014000": "Leite e creme de leite, gordura > 6%",
    "04015010": "Leite e creme de leite, gordura > 6%, acondic. <= 2kg",
    "04021010": "Leite em po, gordura <= 1,5%",
    "04022110": "Leite em po, sem adicao de acucar, gordura > 1,5%",
    "04031000": "Iogurte",
    "04041000": "Soro de leite",
    "04051000": "Manteiga",
    "04061000": "Queijo fresco (nao curado)",
    "04069010": "Mussarela",
    "04070011": "Ovos de galinha, fecundados",
    "04070019": "Outros ovos de ave, fecundados",
    "04090000": "Mel natural",
    "05040011": "Tripas de bovino",
    "05111000": "Semen de bovino",
    "06024000": "Roseiras, enxertadas ou nao",
    "07019000": "Batatas frescas/refrigeradas",
    "07020000": "Tomates frescos/refrigerados",
    "07031019": "Cebolas frescas/refrigeradas",
    "07041000": "Couve-flor e brocolis",
    "07061000": "Cenouras e nabos",
    "07081000": "Ervilhas frescas",
    "07089100": "Alcachofras",
    "07096000": "Pimentoes (Capsicum/Pimenta)",
    "07099100": "Alcachofras",
    "07101000": "Batatas congeladas",
    "07133319": "Feijao preto",
    "07133399": "Outros feijoes",
    "08030000": "Bananas frescas ou secas",
    "08051000": "Laranjas frescas/secas",
    "08052100": "Mandarinas/tangerinas frescas/secas",
    "08061000": "Uvas frescas",
    "08071100": "Melancias",
    "08081000": "Macas frescas",
    "08083000": "Peras frescas",
    "08109010": "Castanha de caju fresca",
    "08109020": "Manga fresca",
    "09011110": "Cafe nao torrado, nao descafeinado, em grao",
    "09011190": "Outro cafe nao torrado, nao descafeinado",
    "09012100": "Cafe torrado nao descafeinado",
    "09024000": "Cha preto fermentado",
    "09042110": "Pimenta seca, nao triturada",
    "10011100": "Trigo duro para semeadura",
    "10019900": "Outros trigos e misturas",
    "10051000": "Milho para semeadura",
    "10059010": "Milho em grao, exceto para semeadura",
    "10059090": "Outros milhos",
    "10061011": "Arroz com casca (paddy) para semeadura",
    "10063011": "Arroz semibranqueado, parboilizado",
    "10063021": "Arroz semibranqueado, nao parboilizado",
    "11010010": "Farinha de trigo",
    "11022000": "Farinha de milho",
    "11071010": "Malte nao torrado, inteiro/partido",
    "12010010": "Soja para semeadura",
    "12019000": "Soja, exceto para semeadura",
    "12024200": "Amendoim descascado",
    "12074010": "Sementes de gergelim",
    "13021100": "Suco de opium",
    "14049090": "Outros produtos vegetais",
    "15079011": "Oleo de soja, refinado, em recipientes < 5L",
    "15079019": "Oleo de soja, refinado, outros",
    "15091000": "Azeite de oliva virgem",
    "15099000": "Outros azeites de oliva",
    "15121110": "Oleo de girassol, bruto",
    "15131100": "Oleo de coco bruto",
    "15171000": "Margarina",
    "16010000": "Enchidos e produtos semelhantes de carne",
    "16024100": "Preparacoes de pernis de suino",
    "16025000": "Preparacoes de carne bovina",
    "17011400": "Outros acucares de cana",
    "17019900": "Outros acucares, incluindo invertido",
    "17049010": "Chocolate branco",
    "18010000": "Cacau inteiro, quebrado, cru/torrado",
    "18063100": "Chocolate recheado",
    "18069000": "Outros chocolates e preparacoes com cacau",
    "19011010": "Preparacoes para alimentacao de criancas",
    "19021100": "Massas nao cozidas, contendo ovos",
    "19021900": "Outras massas nao cozidas",
    "19053100": "Biscoitos doces (cookies)",
    "19059020": "Bolos industrializados",
    "20091100": "Suco de laranja, congelado",
    "20091200": "Suco de laranja, nao congelado, Brix <= 20",
    "20098900": "Outros sucos de fruta",
    "21011110": "Cafe soluvel",
    "21069090": "Outras preparacoes alimenticias",
    "22011000": "Aguas minerais e gaseificadas",
    "22019000": "Outras aguas nao adocadas",
    "22021000": "Aguas com adicao de acucar",
    "22030000": "Cervejas de malte",
    "22041000": "Vinhos espumantes",
    "22042100": "Vinhos em recipientes <= 2L",
    "22071000": "Alcool etilico >= 80%",
    "22084000": "Rum e tafia",
    "22089000": "Outros destilados",
    "23040010": "Farinhas e pellets de soja",
    "23099010": "Preparacoes para caes ou gatos",
    "24012030": "Tabaco nao manufaturado, parcialm. destalado",
    "24022000": "Cigarros contendo tabaco",
    "25010011": "Sal marinho",
    "25010019": "Outro sal (exceto para mesa)",
    "25051000": "Areias siliciosas",
    "25232900": "Cimento Portland, outros",
    "25309000": "Outros minerais",
    "26011100": "Minerio de ferro nao aglomerado",
    "27011200": "Hulha betuminosa",
    "27090010": "Petroleo bruto",
    "27101159": "Outras gasolinas",
    "27101241": "Oleo diesel B (mistura biodiesel)",
    "27101259": "Outros oleos combustiveis",
    "27101921": "Lubrificantes",
    "27111100": "Gas natural liquefeito",
    "27111300": "Butano liquefeito",
    "27112100": "Gas natural em estado gasoso",
    "28112100": "Dioxido de carbono (CO2)",
    "28151100": "Hidroxido de sodio (soda caustica) solido",
    "28170010": "Oxido de zinco",
    "28362000": "Carbonato dissodico",
    "29012100": "Etileno",
    "29012200": "Propeno",
    "29024100": "O-xileno",
    "29051100": "Metanol (alcool metilico)",
    "29053100": "Etilenoglicol",
    "30021200": "Antissoros e fracoes do sangue",
    "30023000": "Vacinas para medicina veterinaria",
    "30042019": "Outros medicamentos com antibioticos",
    "30043100": "Medicamentos contendo insulina",
    "30043999": "Outros medicamentos com hormonios",
    "30049039": "Outros medicamentos em doses",
    "30049069": "Outros medicamentos, nao em doses",
    "30049099": "Outros medicamentos para venda a retalho",
    "30051010": "Pensos adesivos (curativos)",
    "30059090": "Outros artigos farmaceuticos",
    "31021000": "Ureia",
    "31031100": "Superfosfatos, >= 35% P2O5",
    "31052000": "Adubos minerais, com N, P e K",
    "31059090": "Outros adubos",
    "32089090": "Outras tintas e vernizes",
    "32091000": "Tintas a base de polimeros acrilicos",
    "33030010": "Perfumes",
    "33041000": "Produtos de maquiagem para labios",
    "33049100": "Pos, incluidos compactos",
    "33051000": "Champus (shampoos)",
    "33061000": "Dentifricios",
    "34011190": "Saboes de toucador",
    "34022000": "Preparacoes tensoativas (detergentes)",
    "35069190": "Outros adesivos",
    "37024410": "Filmes fotograficos",
    "38089199": "Outros inseticidas",
    "38089290": "Outros fungicidas",
    "38089999": "Outros produtos quimicos diversos",
    "38220000": "Reagentes de diagnostico",
    "39011010": "Polietileno, densidade < 0,94, em formas primarias",
    "39012019": "Polietileno, densidade >= 0,94",
    "39021000": "Polipropileno em formas primarias",
    "39023000": "Copolimeros de propileno",
    "39031100": "Poliestireno expansivel",
    "39041000": "PVC nao misturado",
    "39069090": "Outros polimeros acrilicos",
    "39076100": "PET (politereftalato de etileno)",
    "39199000": "Outras chapas auto-adesivas de plastico",
    "39231000": "Caixas, engradados de plastico",
    "39232100": "Sacos de polimeros de etileno",
    "39232990": "Outros sacos de plastico",
    "39241000": "Servicos de mesa de plastico",
    "39269090": "Outros artigos de plastico",
    "40111000": "Pneumaticos novos para automoveis",
    "40112010": "Pneumaticos novos para onibus/caminhoes",
    "40116100": "Pneumaticos novos para uso agricola",
    "40119200": "Outros pneumaticos novos",
    "40139000": "Camaras de ar",
    "41041100": "Couros e peles de bovino, plena flor",
    "41044100": "Couros e peles curtidos de bovino, secos",
    "42021200": "Malas e maletas com superficie de plastico",
    "42023200": "Carteiras e porta-moedas de plastico/textil",
    "43021900": "Peles curtidas ou acabadas",
    "44011100": "Lenha em toras",
    "44012200": "Madeira em estilhas de nao-coniferas",
    "44039900": "Outras madeiras em bruto",
    "44071100": "Madeira de pinheiro, serrada",
    "44079900": "Outras madeiras serradas",
    "44101100": "Paineis de particulas de madeira",
    "44111200": "Paineis de fibra MDF, esp. <= 5mm",
    "44111300": "Paineis de fibra MDF, 5mm < esp. <= 9mm",
    "44111400": "Paineis de fibra MDF, esp. > 9mm",
    "44123300": "Compensados com face de nao-coniferas",
    "47032100": "Pasta quimica de madeira, coniferas, semi-branqueada",
    "48010010": "Papel de jornal em bobinas",
    "48025290": "Outros papeis/cartoes, 40-150 g/m2",
    "48030000": "Papel higienico e semelhantes",
    "48041100": "Kraftliner cru, nao revestido",
    "48051100": "Papel fluting semi-quimico",
    "48191000": "Caixas de papelao ondulado",
    "48192000": "Caixas dobraveis de papelao nao ondulado",
    "49011000": "Livros, brochuras, impressos",
    "49019900": "Outros livros, folhetos impressos",
    "52010010": "Algodao nao cardado nem penteado",
    "52030000": "Algodao cardado ou penteado",
    "52051100": "Fios de algodao, >= 85%, simples",
    "52082100": "Tecidos de algodao, branqueados, tela",
    "54024600": "Fios de poliester, parcialmente orientados",
    "54077100": "Tecidos de poliester, >= 85%",
    "55032000": "Fibras de poliester descontinuas",
    "56012100": "Algodao hidrófilo e artigos de algodao",
    "60062100": "Tecidos de malha de algodao",
    "61034200": "Calcas de algodao, de malha, masculinas",
    "61046200": "Calcas de algodao, de malha, femininas",
    "61051000": "Camisas de malha, masculinas, algodao",
    "61061000": "Camisas de malha, femininas, algodao",
    "61091000": "Camisetas (T-shirts) de malha, algodao",
    "61099000": "Outras camisetas de malha",
    "61112000": "Vestuario para bebes, de algodao, malha",
    "61159600": "Meias de fibras sinteticas",
    "62033200": "Paletós e blazers de algodao, masculinos",
    "62034200": "Calcas de algodao, masculinas",
    "62042200": "Conjuntos de algodao, femininos",
    "62046200": "Calcas de algodao, femininas",
    "62052000": "Camisas de algodao, masculinas",
    "62114200": "Vestuario feminino de algodao",
    "63021000": "Roupas de cama, de malha",
    "63053300": "Sacos para embalagem, de polietileno",
    "64019200": "Calcados impermeáveis cobrindo tornozelo",
    "64021200": "Calcados de esqui",
    "64029990": "Outros calcados com sola de borracha",
    "64041100": "Calcados para esporte, com sola de borracha",
    "64041900": "Outros calcados com parte superior de textil",
    "64052000": "Outros calcados com parte superior de textil",
    "65050090": "Outros chapeus e artigos de uso semelhante",
    "66019100": "Guarda-chuvas telescopicos",
    "68022100": "Mármores trabalhados",
    "68091100": "Chapas de gesso nao ornamentadas",
    "69072100": "Ladrilhos ceramicos, absorcao de agua <= 0,5%",
    "69089000": "Outros ladrilhos e azulejos ceramicos",
    "69111000": "Artigos para mesa de porcelana",
    "70051000": "Vidro float, polido, com camada absorvente",
    "70099200": "Espelhos de vidro, emoldurados",
    "70109021": "Garrafas de vidro, capacidade > 0,33L",
    "70134200": "Artigos de vidro para mesa, chumbo >= 24%",
    "71081300": "Ouro em outras formas semi-manufaturadas",
    "71131100": "Artigos de joalharia de prata",
    "71171100": "Abotoaduras de metais comuns",
    "72061000": "Ferro e aco nao-ligado em lingotes",
    "72082500": "Produtos laminados a quente, esp. >= 4,75mm",
    "72083900": "Outros laminados a quente, esp. < 3mm",
    "72091600": "Laminados a frio, 1mm < esp. < 3mm",
    "72104900": "Outros laminados revestidos de zinco",
    "72142000": "Barras de ferro/aco, laminadas a quente",
    "72163100": "Perfis U de ferro/aco, laminados a quente",
    "72193200": "Laminados planos de aco inoxidavel, 3mm-4,75mm",
    "73021000": "Trilhos de ferro/aco",
    "73042900": "Outros tubos de revestimento de aco",
    "73063000": "Outros tubos soldados de ferro/aco",
    "73089090": "Outras construcoes de ferro/aco",
    "73110000": "Recipientes de ferro/aco para gas comprimido",
    "73141400": "Telas metalicas de aco inoxidavel",
    "73181500": "Outros parafusos e pinos",
    "74031100": "Catodos de cobre refinado",
    "74081100": "Fios de cobre refinado",
    "76011000": "Aluminio nao ligado em formas brutas",
    "76061200": "Chapas de liga de aluminio, esp. > 0,2mm",
    "76071110": "Folhas de aluminio, laminadas, esp. < 0,2mm",
    "76151000": "Artigos de mesa de aluminio",
    "76161000": "Tachas, pregos de aluminio",
    "79011100": "Zinco nao ligado, >= 99,99%",
    "83024100": "Guarnicoes de metais comuns para moveis",
    "83062100": "Estatuetas de metais comuns",
    "84051000": "Geradores de gas",
    "84099190": "Outras partes para motores de pistao",
    "84133010": "Bombas de combustivel para motores",
    "84137010": "Bombas centrifugas",
    "84186990": "Outros equipamentos de refrigeracao",
    "84189900": "Partes de refrigeradores/congeladores",
    "84211100": "Desnatadeiras centrifugas",
    "84212300": "Filtros de oleo para motores",
    "84221100": "Maquinas de lavar louca domesticas",
    "84501100": "Maquinas de lavar roupa, automaticas, <= 10kg",
    "84501200": "Outras maquinas de lavar roupa, <= 10kg",
    "84713012": "Computadores portateis (notebooks) <= 10 kg",
    "84713019": "Outros computadores portateis",
    "84714100": "Outras maquinas de processamento de dados",
    "84714900": "Outros computadores apresentados em sistemas",
    "84715010": "Unidades de processamento digitais",
    "84716052": "Teclados",
    "84716053": "Dispositivos apontadores (mouse)",
    "84717012": "Unidades de discos magneticos (HDD)",
    "84717019": "Outras unidades de memoria",
    "84718000": "Outras unidades de maquinas de processamento",
    "84733020": "Partes de maquinas de processamento de dados",
    "84798999": "Outras maquinas e aparelhos mecanicos",
    "85015110": "Motores eletricos, CA, polifasicos, <= 750W",
    "85030090": "Partes de motores/geradores eletricos",
    "85044090": "Outros conversores estaticos",
    "85171200": "Telefones celulares e redes sem fio",
    "85176200": "Aparelhos para recepcao/conversao de voz/imagem/dados",
    "85177000": "Partes de aparelhos telefonicos",
    "85182100": "Alto-falante unico montado",
    "85232110": "Cartoes de memoria (fitas magneticas)",
    "85234910": "Discos opticos para gravacao",
    "85238000": "Outros suportes para gravacao",
    "85258019": "Outras cameras de televisao",
    "85285100": "Monitores com tubo de raios catodicos",
    "85285210": "Monitores LCD",
    "85286200": "Projetores",
    "85340000": "Circuitos impressos",
    "85411000": "Diodos (exceto fotodiodos/LED)",
    "85421000": "Cartoes com circuito integrado (smart cards)",
    "85423100": "Processadores e controladores",
    "85423200": "Memorias",
    "85423900": "Outros circuitos integrados",
    "85437099": "Outros aparelhos eletricos",
    "85444200": "Outros condutores eletricos, <= 1000V, com conectores",
    "86071100": "Bogies motores de locomotivas",
    "87011000": "Tratores de eixo simples",
    "87019490": "Outros tratores, potencia > 130cv",
    "87021000": "Veiculos de transporte >= 10 pessoas, diesel",
    "87032100": "Automoveis, cilindrada <= 1000cm3",
    "87032310": "Automoveis, 1500-3000cm3",
    "87033100": "Automoveis diesel, cilindrada <= 1500cm3",
    "87041010": "Dumpers para uso fora de rodovias",
    "87042100": "Veiculos de carga, diesel, PBT <= 5t",
    "87042290": "Outros veiculos de carga, diesel, 5-20t",
    "87060010": "Chassis com motor para veiculos de passageiros",
    "87071000": "Carrocerias para automoveis",
    "87082999": "Outras partes de carrocerias",
    "87083090": "Outros freios e partes",
    "87084090": "Outras caixas de marchas",
    "87085099": "Outros eixos e partes",
    "87089990": "Outras partes e acessorios de veiculos",
    "87112000": "Motocicletas 50-250cm3",
    "87141000": "Partes de motocicletas",
    "88024000": "Avioes, peso vazio > 15000kg",
    "88033000": "Partes de avioes/helicopteros",
    "89039200": "Barcos a motor (exceto popa), comprimento > 7,5m",
    "89052000": "Plataformas de perfuracao flutuantes",
    "90011000": "Fibras opticas",
    "90049000": "Outros oculos",
    "90181200": "Aparelhos de ultrasonografia",
    "90181990": "Outros aparelhos de eletrodiagnostico",
    "90183100": "Seringas",
    "90183210": "Agulhas tubulares de metal",
    "90183929": "Outros cateteres",
    "90189099": "Outros instrumentos medicos/cirurgicos",
    "90191010": "Aparelhos de mecanoterapia",
    "90211000": "Aparelhos ortopedicos",
    "90221200": "Aparelhos de tomografia computadorizada",
    "90221400": "Outros aparelhos de raios X",
    "90268000": "Outros instrumentos de medida de liquidos/gases",
    "90318099": "Outros instrumentos de medida",
    "91021100": "Relogios de pulso, com visor mecânico",
    "91022900": "Outros relogios de pulso",
    "92011000": "Pianos verticais",
    "92029000": "Outros instrumentos de cordas",
    "93020000": "Revolveres e pistolas",
    "93063000": "Outros cartuchos e suas partes",
    "94011000": "Assentos para aeronaves",
    "94012000": "Assentos para veiculos automotores",
    "94017900": "Outros assentos com armacao de metal",
    "94032000": "Outros moveis de metal",
    "94034000": "Moveis de cozinha de madeira",
    "94035000": "Moveis de quarto de madeira",
    "94036000": "Outros moveis de madeira",
    "94042100": "Colchoes de borracha alveolar",
    "94051000": "Lustres e outros aparelhos de iluminacao",
    "95030021": "Triciclos, patinetes, carros de pedais",
    "95030031": "Outros brinquedos, com motor",
    "95030099": "Outros brinquedos",
    "95042000": "Bilhares e acessorios",
    "95066200": "Bolas inflaveis",
    "96032100": "Escovas de dentes",
    "96081000": "Canetas esferograficas",
    "96089200": "Canetas com ponta de feltro",
    "96190000": "Absorventes e tampos higienicos",
}
