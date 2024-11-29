import numpy as np
import pandas as pd
from bs4  import BeautifulSoup
import requests
import time
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")
import sys
import json
from json import loads, dumps
import lxml
from requests import ConnectionError, ReadTimeout, ConnectTimeout, HTTPError, Timeout
import xml
import re
from natsort import natsorted
import xml.etree.ElementTree as ET
import xmltodict
from xml.parsers.expat import ExpatError
from requests.exceptions import ChunkedEncodingError

# ewc stands for "Events we care about."

ewc = ['SHOT', 'HIT', 'BLOCK', 'MISS', 'GIVE', 'TAKE', 'GOAL']

def scrape_schedule_one_week(start_date):
    
    url = f'https://api-web.nhle.com/v1/schedule/{start_date}'
    page = requests.get(url, timeout = 500)
    loaddict = json.loads(page.content)
    
    game_df = pd.DataFrame()

    for i in range(0, (len(loaddict['gameWeek']))):
        #print(i)
        game_day = loaddict['gameWeek'][i]
        game_df = game_df._append(pd.DataFrame(game_day['games']).assign(date = game_day['date']).rename(columns = {'id':'ID'}))

    home_df = pd.DataFrame(game_df['homeTeam'].values.tolist())
    away_df = pd.DataFrame(game_df['awayTeam'].values.tolist())

    game_df = game_df.assign(
        home_team = game_df.homeTeam.apply(lambda x: x['abbrev']),
        away_team = game_df.awayTeam.apply(lambda x: x['abbrev'])
    )

    game_df = game_df.assign(state = np.where(game_df.gameState=='OFF', 'Final',
                               np.where(game_df.gameState=='FUT', 'Scheduled',
                                       np.where(game_df.gameState=='LIVE', 'In Progress',
                                               'Error'))))

    game_df = game_df.assign(type = np.where(game_df.gameType==2, 'R', 'Error'),
                        venue = game_df['venue'].apply(lambda x: x['default']))

    game_df = game_df.assign(ID = game_df.ID.astype(int), season = game_df.season.astype(int))

    schedule = game_df.loc[:, ['ID', 'type', 'season', 'date', 'home_team', 'away_team', 'state']]

    return schedule

def scrape_full_schedule(
        start_date = '2023-10-07',
        end_date = '2024-04-18'):

    full_schedule = pd.DataFrame()

    scrape_day = start_date

    while scrape_day <= end_date:

        print(scrape_day)

        week_scrape = scrape_schedule_one_week(scrape_day)

        full_schedule = full_schedule._append(week_scrape)

        last_day_scraped = max(full_schedule.date)

        scrape_day = datetime.strftime((datetime.strptime(last_day_scraped, '%Y-%m-%d').date() + timedelta(days = 1)), '%Y-%m-%d')

    return full_schedule[full_schedule.type=='R']

def scrape_standings(season):
    """
    Takes an integer in "20202021" form and scrapes standings for that season.
    """
    url = 'https://statsapi.web.nhl.com/api/v1/standings?season=' + str(season)
    page = requests.get(url, timeout = 500)
    loaddict = json.loads(page.content)
    record_df = pd.DataFrame(loaddict['records'])
    team = []
    wins = []
    losses = []
    otl = []
    rw = []
    ga = []
    gf = []
    row = []
    gp = []
    pts = []
    divisions = []
    conferences = []

    for i in range(0, len(record_df['teamRecords'])):
        div = (record_df['division'].iloc[i]['name'])
        conf = (record_df['conference'].iloc[i]['name'])
        for x in range(0, len((record_df['teamRecords'].iloc[i]))):
            divisions._append(div)
            conferences._append(conf)
            team._append(record_df['teamRecords'].iloc[i][x]['team']['name'])
            wins._append(record_df['teamRecords'].iloc[i][x]['leagueRecord']['wins'])
            losses._append(record_df['teamRecords'].iloc[i][x]['leagueRecord']['losses'])
            otl._append(record_df['teamRecords'].iloc[i][x]['leagueRecord']['ot'])
            gf._append(record_df['teamRecords'].iloc[i][x]['goalsScored'])
            ga._append(record_df['teamRecords'].iloc[i][x]['goalsAgainst'])
            if season>20092010:
                row._append(record_df['teamRecords'].iloc[i][x]['row'])
            gp._append(record_df['teamRecords'].iloc[i][x]['gamesPlayed'])
            pts._append(record_df['teamRecords'].iloc[i][x]['points'])
            if season>20192020:
                rw._append(record_df['teamRecords'].iloc[i][x]['regulationWins'])
                
    if season < 20092010:
        stand = pd.DataFrame().assign(Team = team, Division = divisions, Conference = conferences,
                                      GP = gp, W = wins, L = losses, OTL = otl, PTS = pts,  GF = gf, GA = ga)
        stand = stand.assign(GD = stand.GF - stand.GA).sort_values(by = ['PTS', 'GD'], ascending = False)
        return stand.assign(Season = season).loc[:, ['Season', 'Team', 'Division', 'Conference', 'GP', 'W', 'L', 'OTL', 'PTS', 'GF','GA', 'GD']].reset_index(drop = True)
            
    if ((season<20202021) & (season>20092010)):
        stand = pd.DataFrame().assign(Team = team, Division = divisions, Conference = conferences,
                                      GP = gp, W = wins, L = losses, OTL = otl, PTS = pts,  GF = gf, GA = ga, ROW = row)
        stand = stand.assign(GD = stand.GF - stand.GA).sort_values(by = ['PTS', 'ROW', 'GD'], ascending = False)
        return stand.assign(Season = season).loc[:, ['Season', 'Team', 'Division', 'Conference', 'GP', 'W', 'L', 'OTL', 'PTS', 'GF','GA', 'ROW', 'GD']].reset_index(drop = True)
    
    else:
        stand = pd.DataFrame().assign(Team = team, Division = divisions, Conference = conferences, 
                                      GP = gp, W = wins, L = losses, OTL = otl, PTS = pts,  GF = gf, GA = ga, RW = rw, ROW = row)
        stand = stand.assign(GD = stand.GF - stand.GA).sort_values(by = ['PTS', 'RW', 'ROW', 'GD'], ascending = False)
        return stand.assign(Season = season).loc[:, ['Season', 'Team', 'Division', 'Conference', 'GP', 'W', 'L', 'OTL', 'PTS', 'GF','GA', 'RW', 'ROW', 'GD']].reset_index(drop = True)

def scrape_schedule(start_date, end_date):
    
    """
    Scrape the NHL's API and get a schedule back.
    """
    
    url = 'https://statsapi.web.nhl.com/api/v1/schedule?startDate=' + start_date + '&endDate=' + end_date
    page = requests.get(url, timeout = 500)
    loaddict = json.loads(page.content)
    date_list = (loaddict['dates'])
    date_df = pd.DataFrame(date_list)
    
    gamedf = pd.DataFrame()

    for i in range (0, len(date_df)):
        datedf = pd.DataFrame(date_df.games.iloc[i])
        gamedf = gamedf._append(datedf)
    global team_df
    team_df = pd.DataFrame(gamedf['teams'].values.tolist(), index = gamedf.index)
    away_df = pd.DataFrame(team_df['away'].values.tolist(), index = team_df.index)
    home_df = pd.DataFrame(team_df['home'].values.tolist(), index = team_df.index)
    away_team_df = pd.DataFrame(away_df['team'].values.tolist(), index = away_df.index)
    home_team_df = pd.DataFrame(home_df['team'].values.tolist(), index = home_df.index)

    gamedf = gamedf.assign(
        state = pd.DataFrame(gamedf['status'].values.tolist(), index = gamedf.index)['detailedState'],
        homename = home_team_df['name'],
        homeid = home_team_df['id'],
        homescore = home_df['score'],
        awayname = away_team_df['name'],
        awayid = away_team_df['id'],
        awayscore = away_df['score'],
        venue = pd.DataFrame(gamedf['venue'].values.tolist(), index = gamedf.index)['name'],
        gameDate = pd.to_datetime(gamedf['gameDate']).dt.tz_convert('EST')
    )

    gamedf = gamedf.loc[:, ['gamePk', 'link', 'gameType', 'season', 'gameDate','homeid', 'homename',  'homescore','awayid', 'awayname',  'awayscore', 'state', 'venue']].rename(
        columns = {'gamePk':'ID', 'gameType':'type', 'gameDate':'date'})
    
    gamedf['type']

    return(gamedf)

def hs_strip_html(td):
    """
    Function from Harry Shomer's Github
    
    Strip html tags and such 
    
    :param td: pbp
    
    :return: list of plays (which contain a list of info) stripped of html
    """
    for y in range(len(td)):
        # Get the 'br' tag for the time column...this get's us time remaining instead of elapsed and remaining combined
        if y == 3:
            td[y] = td[y].get_text()   # This gets us elapsed and remaining combined-< 3:0017:00
            index = td[y].find(':')
            td[y] = td[y][:index+3]
        elif (y == 6 or y == 7) and td[0] != '#':
            # 6 & 7-> These are the player 1 ice one's
            # The second statement controls for when it's just a header
            baz = td[y].find_all('td')
            bar = [baz[z] for z in range(len(baz)) if z % 4 != 0]  # Because of previous step we get repeats...delete some

            # The setup in the list is now: Name/Number->Position->Blank...and repeat
            # Now strip all the html
            players = []
            for i in range(len(bar)):
                if i % 3 == 0:
                    try:
                        name = return_name_html(bar[i].find('font')['title'])
                        number = bar[i].get_text().strip('\n')  # Get number and strip leading/trailing newlines
                    except KeyError:
                        name = ''
                        number = ''
                elif i % 3 == 1:
                    if name != '':
                        position = bar[i].get_text()
                        players._append([name, number, position])

            td[y] = players
        else:
            td[y] = td[y].get_text()

    return td

def group_if_not_none(result):
    if result is not None:
        result = result.group()
    return(result)

def scrape_html_roster(season, game_id):
    url = 'http://www.nhl.com/scores/htmlreports/' + season + '/RO0' + game_id + '.HTM'
    page = requests.get(url)
    soup = BeautifulSoup(page.content.decode('ISO-8859-1'), 'lxml', multi_valued_attributes = None)
    
    teamsoup = soup.find_all('td', {'align':'center', 'class':['teamHeading + border', 'teamHeading + border '], 'width':'50%'})
    away_team = teamsoup[0].get_text()
    home_team = teamsoup[1].get_text()
    
    home_player_soup = (soup.find_all('table', {'align':'center', 'border':'0', 'cellpadding':'0', 
                        'cellspacing':'0', 'width':'100%', 'xmlns:ext':''}))[1].find_all('td')

    length = int(len(home_player_soup)/3)

    home_player_df = pd.DataFrame(np.array(home_player_soup).reshape(length, 3))

    home_player_df.columns = home_player_df.iloc[0]

    home_player_df = home_player_df.drop(0).assign(team = 'home', team_name = home_team)

    away_player_soup = (soup.find_all('table', {'align':'center', 'border':'0', 'cellpadding':'0', 
                            'cellspacing':'0', 'width':'100%', 'xmlns:ext':''}))[0].find_all('td')

    length = int(len(away_player_soup)/3)

    away_player_df = pd.DataFrame(np.array(away_player_soup).reshape(length, 3))

    away_player_df.columns = away_player_df.iloc[0]

    away_player_df = away_player_df.drop(0).assign(team = 'away', team_name = away_team)
    
    #global home_scratch_soup
    
    if len(soup.find_all('table', {'align':'center', 'border':'0', 'cellpadding':'0', 
                            'cellspacing':'0', 'width':'100%', 'xmlns:ext':''}))>3:

        home_scratch_soup = (soup.find_all('table', {'align':'center', 'border':'0', 'cellpadding':'0', 
                                'cellspacing':'0', 'width':'100%', 'xmlns:ext':''}))[3].find_all('td')
    
        if len(home_scratch_soup)>1:

            length = int(len(home_scratch_soup)/3)

            home_scratch_df = pd.DataFrame(np.array(home_scratch_soup).reshape(length, 3))

            home_scratch_df.columns = home_scratch_df.iloc[0]

            home_scratch_df = home_scratch_df.drop(0).assign(team = 'home', team_name = home_team)

    if 'home_scratch_df' not in locals():
        
        home_scratch_df = pd.DataFrame()
        
    if len(soup.find_all('table', {'align':'center', 'border':'0', 'cellpadding':'0', 
                            'cellspacing':'0', 'width':'100%', 'xmlns:ext':''}))>2:
    
        away_scratch_soup = (soup.find_all('table', {'align':'center', 'border':'0', 'cellpadding':'0', 
                                'cellspacing':'0', 'width':'100%', 'xmlns:ext':''}))[2].find_all('td')
        
        if len(away_scratch_soup)>1:

            length = int(len(away_scratch_soup)/3)

            away_scratch_df = pd.DataFrame(np.array(away_scratch_soup).reshape(length, 3))

            away_scratch_df.columns = away_scratch_df.iloc[0]

            away_scratch_df = away_scratch_df.drop(0).assign(team = 'away', team_name = away_team)
        
    if 'away_scratch_df' not in locals():
        
        away_scratch_df = pd.DataFrame()

    player_df = pd.concat([home_player_df, away_player_df]).assign(status = 'player')
    scratch_df = pd.concat([home_scratch_df, away_scratch_df]).assign(status = 'scratch')
    roster_df = pd.concat([player_df, scratch_df])
    
    roster_df = roster_df.assign(team = np.where(roster_df.team=='CANADIENS MONTREAL', 'MONTREAL CANADIENS', roster_df.team))
    
    # FIX NAMES

    roster_df = roster_df.rename(columns = {'Nom/Name':'Name'})
    
    roster_df.Name = roster_df.Name.str.split('(').str[0].str.strip()
    
    # Max Pacioretty doesn't exist in ESPN in 2009-2010, sadly.
    
    roster_df['Name'] = np.where(roster_df['Name'].str.contains('ALEXANDRE '), 
                                roster_df.Name.str.replace('ALEXANDRE ', 'ALEX '),
                                roster_df['Name'])
    
    roster_df['Name'] = np.where(roster_df['Name'].str.contains('ALEXANDER '), 
                                roster_df.Name.str.replace('ALEXANDER ', 'ALEX '),
                                roster_df['Name'])
    
    roster_df['Name'] = np.where(roster_df['Name'].str.contains('CHRISTOPHER '), 
                                roster_df.Name.str.replace('CHRISTOPHER ', 'CHRIS '),
                                roster_df['Name'])
    
    # List of names and fixed from Evolving Hockey Scraper.
    
    roster_df = roster_df.assign(Name = 
    (np.where(roster_df['Name']== "ANDREI KASTSITSYN" , "ANDREI KOSTITSYN",
    (np.where(roster_df['Name']== "AJ GREER" , "A.J. GREER",
    (np.where(roster_df['Name']== "ANDREW GREENE" , "ANDY GREENE",
    (np.where(roster_df['Name']== "ANDREW WOZNIEWSKI" , "ANDY WOZNIEWSKI", 
    (np.where(roster_df['Name']== "ANTHONY DEANGELO" , "TONY DEANGELO",
    (np.where(roster_df['Name']== "BATES (JON) BATTAGLIA" , "BATES BATTAGLIA",
    (np.where(roster_df['Name'].isin(["BJ CROMBEEN", "B.J CROMBEEN", "BRANDON CROMBEEN", "B J CROMBEEN"]) , "B.J. CROMBEEN", 
    (np.where(roster_df['Name']== "BRADLEY MILLS" , "BRAD MILLS",
    (np.where(roster_df['Name']== "CAMERON BARKER" , "CAM BARKER", 
    (np.where(roster_df['Name']== "COLIN (JOHN) WHITE" , "COLIN WHITE",
    (np.where(roster_df['Name']== "CRISTOVAL NIEVES" , "BOO NIEVES",
    (np.where(roster_df['Name']== "CHRIS VANDE VELDE" , "CHRIS VANDEVELDE", 
    (np.where(roster_df['Name']== "DANNY BRIERE" , "DANIEL BRIERE",
    (np.where(roster_df['Name'].isin(["DAN CLEARY", "DANNY CLEARY"]) , "DANIEL CLEARY",
    (np.where(roster_df['Name']== "DANIEL GIRARDI" , "DAN GIRARDI", 
    (np.where(roster_df['Name']== "DANNY O'REGAN" , "DANIEL O'REGAN",
    (np.where(roster_df['Name']== "DANIEL CARCILLO" , "DAN CARCILLO", 
    (np.where(roster_df['Name']== "DAVID JOHNNY ODUYA" , "JOHNNY ODUYA", 
    (np.where(roster_df['Name']== "DAVID BOLLAND" , "DAVE BOLLAND", 
    (np.where(roster_df['Name']== "DENIS JR. GAUTHIER" , "DENIS GAUTHIER",
    (np.where(roster_df['Name']== "DWAYNE KING" , "DJ KING", 
    (np.where(roster_df['Name']== "EDWARD PURCELL" , "TEDDY PURCELL", 
    (np.where(roster_df['Name']== "EMMANUEL FERNANDEZ" , "MANNY FERNANDEZ", 
    (np.where(roster_df['Name']== "EMMANUEL LEGACE" , "MANNY LEGACE", 
    (np.where(roster_df['Name']== "EVGENII DADONOV" , "EVGENY DADONOV", 
    (np.where(roster_df['Name']== "FREDDY MODIN" , "FREDRIK MODIN", 
    (np.where(roster_df['Name']== "FREDERICK MEYER IV" , "FREDDY MEYER",
    (np.where(roster_df['Name']== "HARRISON ZOLNIERCZYK" , "HARRY ZOLNIERCZYK", 
    (np.where(roster_df['Name']== "ILJA BRYZGALOV" , "ILYA BRYZGALOV", 
    (np.where(roster_df['Name']== "JACOB DOWELL" , "JAKE DOWELL",
    (np.where(roster_df['Name']== "JAMES HOWARD" , "JIMMY HOWARD", 
    (np.where(roster_df['Name']== "JAMES VANDERMEER" , "JIM VANDERMEER",
    (np.where(roster_df['Name']== "JAMES WYMAN" , "JT WYMAN",
    (np.where(roster_df['Name']== "JOHN HILLEN III" , "JACK HILLEN",
    (np.where(roster_df['Name']== "JOHN ODUYA" , "JOHNNY ODUYA",
    (np.where(roster_df['Name']== "JOHN PEVERLEY" , "RICH PEVERLEY",
    (np.where(roster_df['Name']== "JONATHAN SIM" , "JON SIM",
    (np.where(roster_df['Name']== "JONATHON KALINSKI" , "JON KALINSKI",
    (np.where(roster_df['Name']== "JONATHAN AUDY-MARCHESSAULT" , "JONATHAN MARCHESSAULT", 
    (np.where(roster_df['Name']== "JOSEPH CRABB" , "JOEY CRABB",
    (np.where(roster_df['Name']== "JOSEPH CORVO" , "JOE CORVO", 
    (np.where(roster_df['Name']== "JOSHUA BAILEY" , "JOSH BAILEY",
    (np.where(roster_df['Name']== "JOSHUA HENNESSY" , "JOSH HENNESSY", 
    (np.where(roster_df['Name']== "JOSHUA MORRISSEY" , "JOSH MORRISSEY",
    (np.where(roster_df['Name']== "JEAN-FRANCOIS JACQUES" , "J-F JACQUES", 
    (np.where(roster_df['Name'].isin(["J P DUMONT", "JEAN-PIERRE DUMONT"]) , "J-P DUMONT", 
    (np.where(roster_df['Name']== "JT COMPHER" , "J.T. COMPHER",
    (np.where(roster_df['Name']== "KRISTOPHER LETANG" , "KRIS LETANG", 
    (np.where(roster_df['Name']== "KRYSTOFER BARCH" , "KRYS BARCH", 
    (np.where(roster_df['Name']== "KRYSTOFER KOLANOS" , "KRYS KOLANOS",
    (np.where(roster_df['Name']== "MARC POULIOT" , "MARC-ANTOINE POULIOT",
    (np.where(roster_df['Name']== "MARTIN ST LOUIS" , "MARTIN ST. LOUIS", 
    (np.where(roster_df['Name']== "MARTIN ST PIERRE" , "MARTIN ST. PIERRE",
    (np.where(roster_df['Name']== "MARTY HAVLAT" , "MARTIN HAVLAT",
    (np.where(roster_df['Name']== "MATTHEW CARLE" , "MATT CARLE", 
    (np.where(roster_df['Name']== "MATHEW DUMBA" , "MATT DUMBA",
    (np.where(roster_df['Name']== "MATTHEW BENNING" , "MATT BENNING", 
    (np.where(roster_df['Name']== "MATTHEW IRWIN" , "MATT IRWIN",
    (np.where(roster_df['Name']== "MATTHEW NIETO" , "MATT NIETO",
    (np.where(roster_df['Name']== "MATTHEW STAJAN" , "MATT STAJAN",
    (np.where(roster_df['Name']== "MAXIM MAYOROV" , "MAKSIM MAYOROV",
    (np.where(roster_df['Name']== "MAXIME TALBOT" , "MAX TALBOT", 
    (np.where(roster_df['Name']== "MAXWELL REINHART" , "MAX REINHART",
    (np.where(roster_df['Name']== "MICHAEL BLUNDEN" , "MIKE BLUNDEN",
    (np.where(roster_df['Name'].isin(["MICHAËL BOURNIVAL", "MICHAÃ\x8bL BOURNIVAL"]), "MICHAEL BOURNIVAL",
    (np.where(roster_df['Name']== "MICHAEL CAMMALLERI" , "MIKE CAMMALLERI", 
    (np.where(roster_df['Name']== "MICHAEL FERLAND" , "MICHEAL FERLAND", 
    (np.where(roster_df['Name']== "MICHAEL GRIER" , "MIKE GRIER",
    (np.where(roster_df['Name']== "MICHAEL KNUBLE" , "MIKE KNUBLE",
    (np.where(roster_df['Name']== "MICHAEL KOMISAREK" , "MIKE KOMISAREK",
    (np.where(roster_df['Name']== "MICHAEL MATHESON" , "MIKE MATHESON",
    (np.where(roster_df['Name']== "MICHAEL MODANO" , "MIKE MODANO",
    (np.where(roster_df['Name']== "MICHAEL RUPP" , "MIKE RUPP",
    (np.where(roster_df['Name']== "MICHAEL SANTORELLI" , "MIKE SANTORELLI", 
    (np.where(roster_df['Name']== "MICHAEL SILLINGER" , "MIKE SILLINGER",
    (np.where(roster_df['Name']== "MITCHELL MARNER" , "MITCH MARNER", 
    (np.where(roster_df['Name']== "NATHAN GUENIN" , "NATE GUENIN",
    (np.where(roster_df['Name']== "NICHOLAS BOYNTON" , "NICK BOYNTON",
    (np.where(roster_df['Name']== "NICHOLAS DRAZENOVIC" , "NICK DRAZENOVIC", 
    (np.where(roster_df['Name']== "NICKLAS BERGFORS" , "NICLAS BERGFORS",
    (np.where(roster_df['Name']== "NICKLAS GROSSMAN" , "NICKLAS GROSSMANN", 
    (np.where(roster_df['Name']== "NICOLAS PETAN" , "NIC PETAN", 
    (np.where(roster_df['Name']== "NIKLAS KRONVALL" , "NIKLAS KRONWALL",
    (np.where(roster_df['Name']== "NIKOLAI ANTROPOV" , "NIK ANTROPOV",
    (np.where(roster_df['Name']== "NIKOLAI KULEMIN" , "NIKOLAY KULEMIN", 
    (np.where(roster_df['Name']== "NIKOLAI ZHERDEV" , "NIKOLAY ZHERDEV",
    (np.where(roster_df['Name']== "OLIVIER MAGNAN-GRENIER" , "OLIVIER MAGNAN",
    (np.where(roster_df['Name']== "PAT MAROON" , "PATRICK MAROON", 
    (np.where(roster_df['Name'].isin(["P. J. AXELSSON", "PER JOHAN AXELSSON"]) , "P.J. AXELSSON",
    (np.where(roster_df['Name'].isin(["PK SUBBAN", "P.K SUBBAN"]) , "P.K. SUBBAN", 
    (np.where(roster_df['Name'].isin(["PIERRE PARENTEAU", "PIERRE-ALEX PARENTEAU", "PIERRE-ALEXANDRE PARENTEAU", "PA PARENTEAU", "P.A PARENTEAU", "P-A PARENTEAU"]) , "P.A. PARENTEAU", 
    (np.where(roster_df['Name']== "PHILIP VARONE" , "PHIL VARONE",
    (np.where(roster_df['Name']== "QUINTIN HUGHES" , "QUINN HUGHES",
    (np.where(roster_df['Name']== "RAYMOND MACIAS" , "RAY MACIAS",
    (np.where(roster_df['Name']== "RJ UMBERGER" , "R.J. UMBERGER",
    (np.where(roster_df['Name']== "ROBERT BLAKE" , "ROB BLAKE",
    (np.where(roster_df['Name']== "ROBERT EARL" , "ROBBIE EARL",
    (np.where(roster_df['Name']== "ROBERT HOLIK" , "BOBBY HOLIK",
    (np.where(roster_df['Name']== "ROBERT SCUDERI" , "ROB SCUDERI",
    roster_df['Name']))))))))))))))))))))))))))))))))))))))))))))))))))))))
    )))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))
    ))))))))))
    
    roster_df['Name'] = (np.where(roster_df['Name']== "RODNEY PELLEY" , "ROD PELLEY",
    (np.where(roster_df['Name']== "SIARHEI KASTSITSYN" , "SERGEI KOSTITSYN",
    (np.where(roster_df['Name']== "SIMEON VARLAMOV" , "SEMYON VARLAMOV", 
    (np.where(roster_df['Name']== "STAFFAN KRONVALL" , "STAFFAN KRONWALL",
    (np.where(roster_df['Name']== "STEVEN REINPRECHT" , "STEVE REINPRECHT",
    (np.where(roster_df['Name']== "TJ GALIARDI" , "T.J. GALIARDI",
    (np.where(roster_df['Name']== "TJ HENSICK" , "T.J. HENSICK",
    (np.where(roster_df['Name'].isin(["TJ OSHIE", "T.J OSHIE"]) , "T.J. OSHIE", 
    (np.where(roster_df['Name']== "TOBY ENSTROM" , "TOBIAS ENSTROM", 
    (np.where(roster_df['Name']== "TOMMY SESTITO" , "TOM SESTITO",
    (np.where(roster_df['Name']== "VACLAV PROSPAL" , "VINNY PROSPAL",
    (np.where(roster_df['Name']== "VINCENT HINOSTROZA" , "VINNIE HINOSTROZA",
    (np.where(roster_df['Name']== "WILLIAM THOMAS" , "BILL THOMAS",
    (np.where(roster_df['Name']== "ZACHARY ASTON-REESE" , "ZACH ASTON-REESE",
    (np.where(roster_df['Name']== "ZACHARY SANFORD" , "ZACH SANFORD",
    (np.where(roster_df['Name']== "ZACHERY STORTINI" , "ZACK STORTINI",
    (np.where(roster_df['Name']== "MATTHEW MURRAY" , "MATT MURRAY",
    (np.where(roster_df['Name']== "J-SEBASTIEN AUBIN" , "JEAN-SEBASTIEN AUBIN",
    (np.where(roster_df['Name'].isin(["J.F. BERUBE", "JEAN-FRANCOIS BERUBE"]) , "J-F BERUBE", 
    (np.where(roster_df['Name']== "JEFF DROUIN-DESLAURIERS" , "JEFF DESLAURIERS", 
    (np.where(roster_df['Name']== "NICHOLAS BAPTISTE" , "NICK BAPTISTE",
    (np.where(roster_df['Name']== "OLAF KOLZIG" , "OLIE KOLZIG",
    (np.where(roster_df['Name']== "STEPHEN VALIQUETTE" , "STEVE VALIQUETTE",
    (np.where(roster_df['Name']== "THOMAS MCCOLLUM" , "TOM MCCOLLUM",
    (np.where(roster_df['Name']== "TIMOTHY JR. THOMAS" , "TIM THOMAS",
    (np.where(roster_df['Name']== "TIM GETTINGER" , "TIMOTHY GETTINGER",
    (np.where(roster_df['Name']== "NICHOLAS SHORE" , "NICK SHORE",
    (np.where(roster_df['Name']== "T.J. TYNAN" , "TJ TYNAN",
    (np.where(roster_df['Name']== "ALEXIS LAFRENI?RE" , "ALEXIS LAFRENIÈRE",
    (np.where(roster_df['Name']== "ALEXIS LAFRENIERE" , "ALEXIS LAFRENIÈRE", 
    (np.where(roster_df['Name']== "ALEXIS LAFRENIÃRE" , "ALEXIS LAFRENIÈRE",
    (np.where(roster_df['Name']== "TIM STUTZLE" , "TIM STÜTZLE",
    (np.where(roster_df['Name']== "TIM ST?TZLE" , "TIM STÜTZLE",
    (np.where(roster_df['Name']== "TIM STÃTZLE" , "TIM STÜTZLE",
    (np.where(roster_df['Name']== "JANI HAKANPÃ\x84Ã\x84" , "JANI HAKANPAA",
    (np.where(roster_df['Name']== "EGOR SHARANGOVICH" , "YEGOR SHARANGOVICH",
    (np.where(roster_df['Name']== "CALLAN FOOTE" , "CAL FOOTE",
    (np.where(roster_df['Name']== "MATTIAS JANMARK-NYLEN" , "MATTIAS JANMARK",
    (np.where(roster_df['Name']== "JOSH DUNNE" , "JOSHUA DUNNE",roster_df['Name'])))))))))))))))))))))))))))))))))))))))))))
    )))))))))))))))))))))))))))))))))))
    
    roster_df['Name'] = np.where((roster_df['Name']=="SEBASTIAN AHO") & (roster_df['Pos']=='D'), 'SEBASTIAN AHO SWE', roster_df['Name'])
    roster_df['Name'] = np.where((roster_df['Name']=="COLIN WHITE") & (roster_df['Pos']=='D'), 'COLIN WHITE CAN', roster_df['Name'])
    roster_df['Name'] = np.where((roster_df['Name']=="SEAN COLLINS") & (roster_df['Pos']=='D'), 'SEAN COLLINS CAN', roster_df['Name'])
    roster_df['Name'] = np.where((roster_df['Name']=="ALEX PICARD") & (roster_df['Pos']!='D'), 'ALEX PICARD F', roster_df['Name'])
    roster_df['Name'] = np.where((roster_df['Name']=="ERIK GUSTAFSSON") & (int(season)<20132014), 'ERIK GUSTAFSSON 88', roster_df['Name'])
    roster_df['Name'] = np.where((roster_df['Name']=="MIKKO LEHTONEN") & (int(season)<20202021), 'MIKKO LEHTONEN F', roster_df['Name'])
    roster_df['Name'] = np.where(roster_df['Name']=='ALEX BARRÃ-BOULET', 'ALEX BARRE-BOULET', roster_df['Name'])
    roster_df['Name'] = np.where(roster_df['Name']=='COLIN', 'COLIN WHITE CAN', roster_df['Name'])

    roster_df['Name'] = (np.where(roster_df['Name']== "JANIS MOSER" , "J.J. MOSER",
        (np.where(roster_df['Name']== "NICHOLAS PAUL" , "NICK PAUL",
        (np.where(roster_df['Name']== "JACOB MIDDLETON" , "JAKE MIDDLETON",
        (np.where(roster_df['Name']== "TOMMY NOVAK" , "THOMAS NOVAK",
        roster_df['Name']))))))))

    roster_df['Name'] = roster_df['Name'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.upper()

    return roster_df 

def scrape_html_shifts(season, game_id):
    
    url = 'http://www.nhl.com/scores/htmlreports/' + season + '/TH0' + game_id + '.HTM'
    page = (requests.get(url))
    soup = BeautifulSoup(page.content.decode('ISO-8859-1'), 'lxml', multi_valued_attributes = None)
    found = soup.find_all('td', {'class':['playerHeading + border', 'lborder + bborder']})
    if len(found)==0:
        raise IndexError('This game has no shift data.')
    thisteam = soup.find('td', {'align':'center', 'class':'teamHeading + border'}).get_text()
    
    goalie_names = ['AARON DELL',
 'AARON SOROCHAN',
 'ADAM HUSKA',
 'ADAM WERNER',
 'ADAM WILCOX',
 'ADIN HILL',
 'AKIRA SCHMID',
 'AL MONTOYA',
 'ALEX AULD',
 "ALEX D'ORIO",
 'ALEX LYON',
 'ALEX NEDELJKOVIC',
 'ALEX PECHURSKI',
 'ALEX SALAK',
 'ALEX STALOCK',
 'ALEXANDAR GEORGIEV',
 'ALEXEI MELNICHUK',
 'ALLEN YORK',
 'ANDERS LINDBACK',
 'ANDERS NILSSON',
 'ANDREI VASILEVSKIY',
 'ANDREW HAMMOND',
 'ANDREW RAYCROFT',
 'ANDREY MAKAROV',
 'ANGUS REDMOND',
 'ANTERO NIITTYMAKI',
 'ANTHONY STOLARZ',
 'ANTOINE BIBEAU',
 'ANTON FORSBERG',
 'ANTON KHUDOBIN',
 'ANTTI NIEMI',
 'ANTTI RAANTA',
 'ARTURS SILOVS',
 'ARTYOM ZAGIDULIN',
 'ARVID SODERBLOM',
 'BEN BISHOP',
 'BEN SCRIVENS',
 'BEN WEXLER',
 'BRAD THIESSEN',
 'BRADEN HOLTBY',
 'BRANDON HALVERSON',
 'BRENT JOHNSON',
 'BRENT KRAHN',
 'BRETT LEONHARDT',
 'BRIAN BOUCHER',
 'BRIAN ELLIOTT',
 'BRIAN FOSTER',
 'BRYAN PITTON',
 'CAL PETERSEN',
 'CALVIN HEETER',
 'CALVIN PETERSEN',
 'CALVIN PICKARD',
 'CAM TALBOT',
 'CAM WARD',
 'CAMERON JOHNSON',
 'CAREY PRICE',
 'CARTER HART',
 'CARTER HUTTON',
 'CASEY DESMITH',
 'CAYDEN PRIMEAU',
 'CEDRICK DESJARDINS',
 'CHAD JOHNSON',
 'CHARLIE LINDGREN',
 'CHET PICKARD',
 'CHRIS BECKFORD-TSEU',
 'CHRIS DRIEDGER',
 'CHRIS GIBSON',
 'CHRIS HOLT',
 'CHRIS MASON',
 'CHRIS OSGOOD',
 'COLE KEHLER',
 'COLLIN DELIA',
 'CONNOR HELLEBUYCK',
 'CONNOR INGRAM',
 'CONNOR KNAPP',
 'COREY CRAWFORD',
 'CORY SCHNEIDER',
 'CRAIG ANDERSON',
 'CRISTOBAL HUET',
 'CRISTOPHER NILSTORP',
 'CURTIS JOSEPH',
 'CURTIS MCELHINNEY',
 'CURTIS SANFORD',
 'DAN CLOUTIER',
 'DAN ELLIS',
 'DAN TURPLE',
 'DAN VLADAR',
 'DANIEL ALTSHULLER',
 'DANIEL LACOSTA',
 'DANIEL LARSSON',
 'DANIEL MANZATO',
 'DANIEL TAYLOR',
 'DANIIL TARASOV',
 'DANY SABOURIN',
 'DARCY KUEMPER',
 'DAREN MACHESNEY',
 'DAVID AEBISCHER',
 'DAVID AYRES',
 'DAVID LENEVEU',
 'DAVID RITTICH',
 'DAVID SHANTZ',
 'DENNIS ENDRAS',
 'DERECK BARIBEAU',
 'DEVAN DUBNYK',
 'DIMITRI PATZOLD',
 'DOMINIK HASEK',
 'DREW MACINTYRE',
 'DUSTIN BUTLER',
 'DUSTIN TOKARSKI',
 'DUSTYN ZENNER',
 'DWAYNE ROLOSON',
 'DYLAN FERGUSON',
 'DYLAN WELLS',
 'EAMON MCADAM',
 'EDDIE LACK',
 'EDWARD PASQUALE',
 'ELVIS MERZLIKINS',
 'EMIL LARMI',
 'ERIC COMRIE',
 'ERIC HARTZELL',
 'ERIC SEMBORSKI',
 'ERIK ERSBERG',
 'EVAN CORMIER',
 'EVAN FITZPATRICK',
 'EVGENI NABOKOV',
 'FELIX SANDSTROM',
 'FILIP GUSTAVSSON',
 'FRED BRATHWAITE',
 'FREDERIC CASSIVI',
 'FREDERIK ANDERSEN',
 'FREDRIK NORRENA',
 'GARRET SPARKS',
 'GAVIN MCHALE',
 'GERALD COLEMAN',
 'GILLES SENN',
 'HANNU TOIVONEN',
 'HARRI SATERI',
 'HENRIK KARLSSON',
 'HENRIK LUNDQVIST',
 'HUGO ALNEFELT',
 'HUNTER MISKA',
 'IGOR BOBKOV',
 'IGOR SHESTERKIN',
 'IIRO TARKKI',
 'ILYA BRYZGALOV',
 'ILYA SAMSONOV',
 'ILYA SOROKIN',
 'IVAN PROSVETOV',
 'J-F BERUBE',
 'J.F. BERUBE',
 'JACK CAMPBELL',
 'JACOB MARKSTROM',
 'JAKE ALLEN',
 'JAKE OETTINGER',
 'JAMES REIMER',
 'JARED COREAU',
 'JAROSLAV HALAK',
 'JASON BACASHIHUA',
 'JASON KASDORF',
 'JASON LABARBERA',
 'JASON MISSIAEN',
 'JEAN-PHILIPPE LEVASSEUR',
 'JEAN-SEBASTIEN AUBIN',
 'JEAN-SEBASTIEN GIGUERE',
 'JEFF DESLAURIERS',
 'JEFF FRAZEE',
 'JEFF GLASS',
 'JEFF TYNI',
 'JEFF ZATKOFF',
 'JEREMY DUCHESNE',
 'JEREMY SMITH',
 'JEREMY SWAYMAN',
 'JHONAS ENROTH',
 'JIMMY HOWARD',
 'JOACIM ERIKSSON',
 'JOCELYN THIBAULT',
 'JOE CANNATA',
 'JOE FALLON',
 'JOEL HOFER',
 'JOEL MARTIN',
 'JOEY DACCORD',
 'JOEY MACDONALD',
 'JOHAN BACKLUND',
 'JOHAN GUSTAFSSON',
 'JOHAN HEDBERG',
 'JOHAN HOLMQVIST',
 'JOHN CURRY',
 'JOHN GIBSON',
 'JOHN GRAHAME',
 'JOHN MUSE',
 'JON GILLIES',
 'JON-PAUL ANDERSON',
 'JONAS GUSTAVSSON',
 'JONAS HILLER',
 'JONAS JOHANSSON',
 'JONATHAN BERNIER',
 'JONATHAN BOUTIN',
 'JONATHAN QUICK',
 'JONI ORTIO',
 'JOONAS KORPISALO',
 'JORDAN BINNINGTON',
 'JORDAN PEARCE',
 'JORDAN SIGALET',
 'JORDAN WHITE',
 'JORGE ALVES',
 'JOSE THEODORE',
 'JOSEF KORENAR',
 'JOSEPH WOLL',
 'JOSH HARDING',
 'JOSH TORDJMAN',
 'JUSSI RYNNAS',
 'JUSTIN KOWALKOSKI',
 'JUSTIN PETERS',
 'JUSTIN POGGE',
 'JUSTUS ANNUNEN',
 'JUUSE SAROS',
 'JUUSO RIKSMAN',
 'KAAPO KAHKONEN',
 'KADEN FULCHER',
 'KAREL VEJMELKA',
 'KARI LEHTONEN',
 'KARRI RAMO',
 'KASIMIR KASKISUO',
 'KEITH KINKAID',
 'KEN APPLEBY',
 'KENNETH APPLEBY',
 'KENT SIMPSON',
 'KEVIN BOYLE',
 'KEVIN LANKINEN',
 'KEVIN MANDOLESE',
 'KEVIN NASTIUK',
 'KEVIN POULIN',
 'KEVIN WEEKES',
 'KRISTERS GUDLEVSKIS',
 'KURTIS MUCHA',
 'LANDON BOW',
 'LARS JOHANSSON',
 'LAURENT BROSSOIT',
 'LELAND IRVING',
 'LINUS ULLMARK',
 'LOGAN THOMPSON',
 'LOUIS DOMINGUE',
 'LUKAS DOSTAL',
 'MACKENZIE BLACKWOOD',
 'MACKENZIE SKAPSKI',
 'MAGNUS HELLBERG',
 'MALCOLM SUBBAN',
 'MANNY FERNANDEZ',
 'MANNY LEGACE',
 'MARC CHEVERIE',
 'MARC DENIS',
 'MARC-ANDRE FLEURY',
 'MARCUS HOGBERG',
 'MAREK LANGHAMER',
 'MAREK MAZANEC',
 'MAREK SCHWARZ',
 'MARK DEKANICH',
 'MARK VISENTIN',
 'MARTIN BIRON',
 'MARTIN BRODEUR',
 'MARTIN GERBER',
 'MARTIN JONES',
 'MARTY TURCO',
 'MAT ROBSON',
 'MATHIEU CORBEIL',
 'MATHIEU GARON',
 'MATISS KIVLENIEKS',
 'MATT CLIMIE',
 'MATT DALTON',
 'MATT HACKETT',
 'MATT KEETLEY',
 'MATT MURRAY',
 'MATT VILLALTA',
 'MATT ZABA',
 'MATTHEW HEWITT',
 "MATTHEW O'CONNOR",
 'MAXIME LAGACE',
 'MICHAEL DIPIETRO',
 'MICHAEL GARTEIG',
 'MICHAEL HOUSER',
 'MICHAEL HUTCHINSON',
 'MICHAEL LEE',
 'MICHAEL LEIGHTON',
 'MICHAEL MCNIVEN',
 'MICHAEL MOLE',
 'MICHAEL MORRISON',
 'MICHAEL WALL',
 'MICHAL NEUVIRTH',
 'MIIKA WIIKMAN',
 'MIIKKA KIPRUSOFF',
 'MIKAEL TELLQVIST',
 'MIKE BRODEUR',
 'MIKE CONDON',
 'MIKE MCKENNA',
 'MIKE MURPHY',
 'MIKE SMITH',
 'MIKKO KOSKINEN',
 'MIROSLAV SVOBODA',
 'NATHAN DEOBALD',
 'NATHAN LAWSON',
 'NATHAN LIEUWEN',
 'NATHAN SCHOENFELD',
 'NICK ELLIS',
 'NICO DAWS',
 'NIKLAS BACKSTROM',
 'NIKLAS LUNDSTROM',
 'NIKLAS SVEDBERG',
 'NIKLAS TREUTLE',
 'NIKOLAI KHABIBULIN',
 'NOLAN SCHAEFER',
 'OLIE KOLZIG',
 'ONDREJ PAVELEC',
 'OSCAR DANSK',
 'PASCAL LECLAIRE',
 'PAT CONACHER',
 'PATRICK KILLEEN',
 'PATRICK LALIME',
 'PAUL DEUTSCH',
 'PAVEL FRANCOUZ',
 'PEKKA RINNE',
 'PETER BUDAJ',
 'PETER MANNINO',
 'PETR MRAZEK',
 'PHEONIX COPLEY',
 'PHILIPP GRUBAUER',
 'PHILIPPE DESROSIERS',
 'RAY EMERY',
 'RETO BERRA',
 'RICHARD BACHMAN',
 'RICK DIPIETRO',
 'RIKU HELENIUS',
 'ROB LAURIE',
 'ROB ZEPP',
 'ROBB  TALLAS',
 'ROBBIE TALLAS',
 'ROBERT MAYER',
 'ROBERTO LUONGO',
 'ROBIN LEHNER',
 'ROMAN WILL',
 'RYAN LOWE',
 'RYAN MILLER',
 'RYAN MUNCE',
 'RYAN VINZ',
 'SAM BRITTAIN',
 'SAM MONTEMBEAULT',
 'SAMI AITTOKALLIO',
 'SAMUEL MONTEMBEAULT',
 'SCOTT CLEMMENSEN',
 'SCOTT DARLING',
 'SCOTT FOSTER',
 'SCOTT MUNROE',
 'SCOTT STAJCER',
 'SCOTT WEDGEWOOD',
 'SEBASTIEN CARON',
 'SEMYON VARLAMOV',
 'SERGEI BOBROVSKY',
 'SHAWN HUNWICK',
 'SPENCER KNIGHT',
 'SPENCER MARTIN',
 'STEFANOS LEKKAS',
 'STEVE MASON',
 'STEVE MICHALEK',
 'STEVE VALIQUETTE',
 'STUART SKINNER',
 'THATCHER DEMKO',
 'THOMAS FENTON',
 'THOMAS GREISS',
 'TIM THOMAS',
 'TIMO PIELMEIER',
 'TIMOTHY JR. THOMAS',
 'TOBIAS STEPHAN',
 'TODD FORD',
 'TOM MCCOLLUM',
 'TOMAS POPPERLE',
 'TOMAS VOKOUN',
 'TORRIE JUNG',
 'TRISTAN JARRY',
 'TROY GROSENICK',
 'TUUKKA RASK',
 'TY CONKLIN',
 'TYLER BUNZ',
 'TYLER PLANTE',
 'TYLER STEWART',
 'TYLER WEIMAN',
 'TYSON SEXSMITH',
 'UKKO-PEKKA LUUKKONEN',
 'VEINI VEHVILAINEN',
 'VESA TOSKALA',
 'VIKTOR FASTH',
 'VILLE HUSSO',
 'VITEK VANECEK',
 'WADE DUBIELEWICZ',
 'YANN DANIS',
 'ZACH FUCALE',
 'ZACH SAWCHENKO',
 'ZACH SIKICH',
 'ZACHARY FUCALE',
 'ZANE KALEMBA',
 'ZANE MCINTYRE']

    players = dict()

    for i in range(len(found)):
        line = found[i].get_text()
        if ', ' in line:
            name = line.split(',')
            number = name[0].split(' ')[0].strip()
            last_name =  name[0].split(' ')[1].strip()
            first_name = name[1].strip()
            full_name = first_name + " " + last_name
            players[full_name] = dict()
            players[full_name]['number'] = number
            players[full_name]['name'] = full_name
            players[full_name]['shifts'] = []
        else:
            players[full_name]['shifts'].extend([line])

    alldf = pd.DataFrame()

    for key in players.keys(): 
        length = int(len(np.array((players[key]['shifts'])))/5)
        df = pd.DataFrame(np.array((players[key]['shifts'])).reshape(length, 5)).rename(
        columns = {0:'shift_number', 1:'period', 2:'shift_start', 3:'shift_end', 4:'duration'})
        df = df.assign(name = players[key]['name'],
                      number = players[key]['number'],
                      team = thisteam,
                      venue = "home")
        alldf = alldf._append(df)
        
    home_shifts = alldf
    
    url = 'http://www.nhl.com/scores/htmlreports/' + season + '/TV0' + game_id + '.HTM'
    page = (requests.get(url))
    soup = BeautifulSoup(page.content.decode('ISO-8859-1'), 'lxml', multi_valued_attributes = None)
    found = soup.find_all('td', {'class':['playerHeading + border', 'lborder + bborder']})
    thisteam = soup.find('td', {'align':'center', 'class':'teamHeading + border'}).get_text()

    players = dict()

    for i in range(len(found)):
        line = found[i].get_text()
        if ', ' in line:
            name = line.split(',')
            number = name[0].split(' ')[0].strip()
            last_name =  name[0].split(' ')[1].strip()
            first_name = name[1].strip()
            full_name = first_name + " " + last_name
            players[full_name] = dict()
            players[full_name]['number'] = number
            players[full_name]['name'] = full_name
            players[full_name]['shifts'] = []
        else:
            players[full_name]['shifts'].extend([line])

    alldf = pd.DataFrame()

    for key in players.keys(): 
        length = int(len(np.array((players[key]['shifts'])))/5)
        df = pd.DataFrame(np.array((players[key]['shifts'])).reshape(length, 5)).rename(
        columns = {0:'shift_number', 1:'period', 2:'shift_start', 3:'shift_end', 4:'duration'})
        df = df.assign(name = players[key]['name'],
                      number = players[key]['number'],
                      team = thisteam,
                      venue = "away")
        alldf = alldf._append(df)

    away_shifts = alldf
    
    global all_shifts
    
    all_shifts = pd.concat([home_shifts, away_shifts])
    
    all_shifts = all_shifts.assign(start_time = all_shifts.shift_start.str.split('/').str[0])
    
    all_shifts = all_shifts.assign(end_time = all_shifts.shift_end.str.split('/').str[0])
    
    #all_shifts = all_shifts[~all_shifts.end_time.str.contains('\xa0')]
    
    all_shifts.period = (np.where(all_shifts.period=='OT', 4, all_shifts.period)).astype(int)
    
    all_shifts = all_shifts.assign(end_time = np.where(~all_shifts.shift_end.str.contains('\xa0'), all_shifts.end_time,
              (np.where(
              (((pd.to_datetime(((60 * (all_shifts.start_time.str.split(':').str[0].astype(int))) + 
              (all_shifts.start_time.str.split(':').str[1].astype(int)) + 
                (60 * (all_shifts.duration.str.split(':').str[0].astype(int))).astype(int) +
              (all_shifts.duration.str.split(':').str[1].astype(int))).astype(int), unit = 's'))).dt.time).astype(str).str[3:].str[0]=='0',
              (((pd.to_datetime(((60 * (all_shifts.start_time.str.split(':').str[0].astype(int))) + 
              (all_shifts.start_time.str.split(':').str[1].astype(int)) + 
                (60 * (all_shifts.duration.str.split(':').str[0].astype(int))).astype(int) +
              (all_shifts.duration.str.split(':').str[1].astype(int))).astype(int), unit = 's'))).dt.time).astype(str).str[4:],
              (((pd.to_datetime(((60 * (all_shifts.start_time.str.split(':').str[0].astype(int))) + 
              (all_shifts.start_time.str.split(':').str[1].astype(int)) + 
                (60 * (all_shifts.duration.str.split(':').str[0].astype(int))).astype(int) +
              (all_shifts.duration.str.split(':').str[1].astype(int))).astype(int), unit = 's'))).dt.time).astype(str).str[4:]))))
    
    all_shifts['name'] = np.where(all_shifts['name'].str.contains('ALEXANDRE '), 
                                all_shifts.name.str.replace('ALEXANDRE ', 'ALEX '),
                                all_shifts['name'])
    
    all_shifts['name'] = np.where(all_shifts['name'].str.contains('ALEXANDER '), 
                                all_shifts.name.str.replace('ALEXANDER ', 'ALEX '),
                                all_shifts['name'])
    
    all_shifts['name'] = np.where(all_shifts['name'].str.contains('CHRISTOPHER '), 
                                all_shifts.name.str.replace('CHRISTOPHER ', 'CHRIS '),
                                all_shifts['name'])
    
    all_shifts = all_shifts.assign(name = 
    (np.where(all_shifts['name']== "ANDREI KASTSITSYN" , "ANDREI KOSTITSYN",
    (np.where(all_shifts['name']== "AJ GREER" , "A.J. GREER",
    (np.where(all_shifts['name']== "ANDREW GREENE" , "ANDY GREENE",
    (np.where(all_shifts['name']== "ANDREW WOZNIEWSKI" , "ANDY WOZNIEWSKI", 
    (np.where(all_shifts['name']== "ANTHONY DEANGELO" , "TONY DEANGELO",
    (np.where(all_shifts['name']== "BATES (JON) BATTAGLIA" , "BATES BATTAGLIA",
    (np.where(all_shifts['name'].isin(["BJ CROMBEEN", "B.J CROMBEEN", "BRANDON CROMBEEN", "B J CROMBEEN"]) , "B.J. CROMBEEN", 
    (np.where(all_shifts['name']== "BRADLEY MILLS" , "BRAD MILLS",
    (np.where(all_shifts['name']== "CAMERON BARKER" , "CAM BARKER", 
    (np.where(all_shifts['name']== "COLIN (JOHN) WHITE" , "COLIN WHITE",
    (np.where(all_shifts['name']== "CRISTOVAL NIEVES" , "BOO NIEVES",
    (np.where(all_shifts['name']== "CHRIS VANDE VELDE" , "CHRIS VANDEVELDE", 
    (np.where(all_shifts['name']== "DANNY BRIERE" , "DANIEL BRIERE",
    (np.where(all_shifts['name'].isin(["DAN CLEARY", "DANNY CLEARY"]) , "DANIEL CLEARY",
    (np.where(all_shifts['name']== "DANIEL GIRARDI" , "DAN GIRARDI", 
    (np.where(all_shifts['name']== "DANNY O'REGAN" , "DANIEL O'REGAN",
    (np.where(all_shifts['name']== "DANIEL CARCILLO" , "DAN CARCILLO", 
    (np.where(all_shifts['name']== "DAVID JOHNNY ODUYA" , "JOHNNY ODUYA", 
    (np.where(all_shifts['name']== "DAVID BOLLAND" , "DAVE BOLLAND", 
    (np.where(all_shifts['name']== "DENIS JR. GAUTHIER" , "DENIS GAUTHIER",
    (np.where(all_shifts['name']== "DWAYNE KING" , "DJ KING", 
    (np.where(all_shifts['name']== "EDWARD PURCELL" , "TEDDY PURCELL", 
    (np.where(all_shifts['name']== "EMMANUEL FERNANDEZ" , "MANNY FERNANDEZ", 
    (np.where(all_shifts['name']== "EMMANUEL LEGACE" , "MANNY LEGACE", 
    (np.where(all_shifts['name']== "EVGENII DADONOV" , "EVGENY DADONOV", 
    (np.where(all_shifts['name']== "FREDDY MODIN" , "FREDRIK MODIN", 
    (np.where(all_shifts['name']== "FREDERICK MEYER IV" , "FREDDY MEYER",
    (np.where(all_shifts['name']== "HARRISON ZOLNIERCZYK" , "HARRY ZOLNIERCZYK", 
    (np.where(all_shifts['name']== "ILJA BRYZGALOV" , "ILYA BRYZGALOV", 
    (np.where(all_shifts['name']== "JACOB DOWELL" , "JAKE DOWELL",
    (np.where(all_shifts['name']== "JAMES HOWARD" , "JIMMY HOWARD", 
    (np.where(all_shifts['name']== "JAMES VANDERMEER" , "JIM VANDERMEER",
    (np.where(all_shifts['name']== "JAMES WYMAN" , "JT WYMAN",
    (np.where(all_shifts['name']== "JOHN HILLEN III" , "JACK HILLEN",
    (np.where(all_shifts['name']== "JOHN ODUYA" , "JOHNNY ODUYA",
    (np.where(all_shifts['name']== "JOHN PEVERLEY" , "RICH PEVERLEY",
    (np.where(all_shifts['name']== "JONATHAN SIM" , "JON SIM",
    (np.where(all_shifts['name']== "JONATHON KALINSKI" , "JON KALINSKI",
    (np.where(all_shifts['name']== "JONATHAN AUDY-MARCHESSAULT" , "JONATHAN MARCHESSAULT", 
    (np.where(all_shifts['name']== "JOSEPH CRABB" , "JOEY CRABB",
    (np.where(all_shifts['name']== "JOSEPH CORVO" , "JOE CORVO", 
    (np.where(all_shifts['name']== "JOSHUA BAILEY" , "JOSH BAILEY",
    (np.where(all_shifts['name']== "JOSHUA HENNESSY" , "JOSH HENNESSY", 
    (np.where(all_shifts['name']== "JOSHUA MORRISSEY" , "JOSH MORRISSEY",
    (np.where(all_shifts['name']== "JEAN-FRANCOIS JACQUES" , "J-F JACQUES", 
    (np.where(all_shifts['name'].isin(["J P DUMONT", "JEAN-PIERRE DUMONT"]) , "J-P DUMONT", 
    (np.where(all_shifts['name']== "JT COMPHER" , "J.T. COMPHER",
    (np.where(all_shifts['name']== "KRISTOPHER LETANG" , "KRIS LETANG", 
    (np.where(all_shifts['name']== "KRYSTOFER BARCH" , "KRYS BARCH", 
    (np.where(all_shifts['name']== "KRYSTOFER KOLANOS" , "KRYS KOLANOS",
    (np.where(all_shifts['name']== "MARC POULIOT" , "MARC-ANTOINE POULIOT",
    (np.where(all_shifts['name']== "MARTIN ST LOUIS" , "MARTIN ST. LOUIS", 
    (np.where(all_shifts['name']== "MARTIN ST PIERRE" , "MARTIN ST. PIERRE",
    (np.where(all_shifts['name']== "MARTY HAVLAT" , "MARTIN HAVLAT",
    (np.where(all_shifts['name']== "MATTHEW CARLE" , "MATT CARLE", 
    (np.where(all_shifts['name']== "MATHEW DUMBA" , "MATT DUMBA",
    (np.where(all_shifts['name']== "MATTHEW BENNING" , "MATT BENNING", 
    (np.where(all_shifts['name']== "MATTHEW IRWIN" , "MATT IRWIN",
    (np.where(all_shifts['name']== "MATTHEW NIETO" , "MATT NIETO",
    (np.where(all_shifts['name']== "MATTHEW STAJAN" , "MATT STAJAN",
    (np.where(all_shifts['name']== "MAXIM MAYOROV" , "MAKSIM MAYOROV",
    (np.where(all_shifts['name']== "MAXIME TALBOT" , "MAX TALBOT", 
    (np.where(all_shifts['name']== "MAXWELL REINHART" , "MAX REINHART",
    (np.where(all_shifts['name']== "MICHAEL BLUNDEN" , "MIKE BLUNDEN",
    (np.where(all_shifts['name'].isin(["MICHAËL BOURNIVAL", "MICHAÃ\x8bL BOURNIVAL"]), "MICHAEL BOURNIVAL",
    (np.where(all_shifts['name']== "MICHAEL CAMMALLERI" , "MIKE CAMMALLERI", 
    (np.where(all_shifts['name']== "MICHAEL FERLAND" , "MICHEAL FERLAND", 
    (np.where(all_shifts['name']== "MICHAEL GRIER" , "MIKE GRIER",
    (np.where(all_shifts['name']== "MICHAEL KNUBLE" , "MIKE KNUBLE",
    (np.where(all_shifts['name']== "MICHAEL KOMISAREK" , "MIKE KOMISAREK",
    (np.where(all_shifts['name']== "MICHAEL MATHESON" , "MIKE MATHESON",
    (np.where(all_shifts['name']== "MICHAEL MODANO" , "MIKE MODANO",
    (np.where(all_shifts['name']== "MICHAEL RUPP" , "MIKE RUPP",
    (np.where(all_shifts['name']== "MICHAEL SANTORELLI" , "MIKE SANTORELLI", 
    (np.where(all_shifts['name']== "MICHAEL SILLINGER" , "MIKE SILLINGER",
    (np.where(all_shifts['name']== "MITCHELL MARNER" , "MITCH MARNER", 
    (np.where(all_shifts['name']== "NATHAN GUENIN" , "NATE GUENIN",
    (np.where(all_shifts['name']== "NICHOLAS BOYNTON" , "NICK BOYNTON",
    (np.where(all_shifts['name']== "NICHOLAS DRAZENOVIC" , "NICK DRAZENOVIC", 
    (np.where(all_shifts['name']== "NICKLAS BERGFORS" , "NICLAS BERGFORS",
    (np.where(all_shifts['name']== "NICKLAS GROSSMAN" , "NICKLAS GROSSMANN", 
    (np.where(all_shifts['name']== "NICOLAS PETAN" , "NIC PETAN", 
    (np.where(all_shifts['name']== "NIKLAS KRONVALL" , "NIKLAS KRONWALL",
    (np.where(all_shifts['name']== "NIKOLAI ANTROPOV" , "NIK ANTROPOV",
    (np.where(all_shifts['name']== "NIKOLAI KULEMIN" , "NIKOLAY KULEMIN", 
    (np.where(all_shifts['name']== "NIKOLAI ZHERDEV" , "NIKOLAY ZHERDEV",
    (np.where(all_shifts['name']== "OLIVIER MAGNAN-GRENIER" , "OLIVIER MAGNAN",
    (np.where(all_shifts['name']== "PAT MAROON" , "PATRICK MAROON", 
    (np.where(all_shifts['name'].isin(["P. J. AXELSSON", "PER JOHAN AXELSSON"]) , "P.J. AXELSSON",
    (np.where(all_shifts['name'].isin(["PK SUBBAN", "P.K SUBBAN"]) , "P.K. SUBBAN", 
    (np.where(all_shifts['name'].isin(["PIERRE PARENTEAU", "PIERRE-ALEX PARENTEAU", "PIERRE-ALEXANDRE PARENTEAU", "PA PARENTEAU", "P.A PARENTEAU", "P-A PARENTEAU"]) , "P.A. PARENTEAU", 
    (np.where(all_shifts['name']== "PHILIP VARONE" , "PHIL VARONE",
    (np.where(all_shifts['name']== "QUINTIN HUGHES" , "QUINN HUGHES",
    (np.where(all_shifts['name']== "RAYMOND MACIAS" , "RAY MACIAS",
    (np.where(all_shifts['name']== "RJ UMBERGER" , "R.J. UMBERGER",
    (np.where(all_shifts['name']== "ROBERT BLAKE" , "ROB BLAKE",
    (np.where(all_shifts['name']== "ROBERT EARL" , "ROBBIE EARL",
    (np.where(all_shifts['name']== "ROBERT HOLIK" , "BOBBY HOLIK",
    (np.where(all_shifts['name']== "ROBERT SCUDERI" , "ROB SCUDERI",
    all_shifts['name']))))))))))))))))))))))))))))))))))))))))))))))))))))))
    )))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))
    ))))))))))
    
    all_shifts['name'] = (np.where(all_shifts['name']== "RODNEY PELLEY" , "ROD PELLEY",
    (np.where(all_shifts['name']== "SIARHEI KASTSITSYN" , "SERGEI KOSTITSYN",
    (np.where(all_shifts['name']== "SIMEON VARLAMOV" , "SEMYON VARLAMOV", 
    (np.where(all_shifts['name']== "STAFFAN KRONVALL" , "STAFFAN KRONWALL",
    (np.where(all_shifts['name']== "STEVEN REINPRECHT" , "STEVE REINPRECHT",
    (np.where(all_shifts['name']== "TJ GALIARDI" , "T.J. GALIARDI",
    (np.where(all_shifts['name']== "TJ HENSICK" , "T.J. HENSICK",
    (np.where(all_shifts['name'].isin(["TJ OSHIE", "T.J OSHIE"]) , "T.J. OSHIE", 
    (np.where(all_shifts['name']== "TOBY ENSTROM" , "TOBIAS ENSTROM", 
    (np.where(all_shifts['name']== "TOMMY SESTITO" , "TOM SESTITO",
    (np.where(all_shifts['name']== "VACLAV PROSPAL" , "VINNY PROSPAL",
    (np.where(all_shifts['name']== "VINCENT HINOSTROZA" , "VINNIE HINOSTROZA",
    (np.where(all_shifts['name']== "WILLIAM THOMAS" , "BILL THOMAS",
    (np.where(all_shifts['name']== "ZACHARY ASTON-REESE" , "ZACH ASTON-REESE",
    (np.where(all_shifts['name']== "ZACHARY SANFORD" , "ZACH SANFORD",
    (np.where(all_shifts['name']== "ZACHERY STORTINI" , "ZACK STORTINI",
    (np.where(all_shifts['name']== "MATTHEW MURRAY" , "MATT MURRAY",
    (np.where(all_shifts['name']== "J-SEBASTIEN AUBIN" , "JEAN-SEBASTIEN AUBIN",
    (np.where(all_shifts['name'].isin(["J.F. BERUBE", "JEAN-FRANCOIS BERUBE"]) , "J-F BERUBE", 
    (np.where(all_shifts['name']== "JEFF DROUIN-DESLAURIERS" , "JEFF DESLAURIERS", 
    (np.where(all_shifts['name']== "NICHOLAS BAPTISTE" , "NICK BAPTISTE",
    (np.where(all_shifts['name']== "OLAF KOLZIG" , "OLIE KOLZIG",
    (np.where(all_shifts['name']== "STEPHEN VALIQUETTE" , "STEVE VALIQUETTE",
    (np.where(all_shifts['name']== "THOMAS MCCOLLUM" , "TOM MCCOLLUM",
    (np.where(all_shifts['name']== "TIMOTHY JR. THOMAS" , "TIM THOMAS",
    (np.where(all_shifts['name']== "TIM GETTINGER" , "TIMOTHY GETTINGER",
    (np.where(all_shifts['name']== "NICHOLAS SHORE" , "NICK SHORE",
    (np.where(all_shifts['name']== "T.J. TYNAN" , "TJ TYNAN",
    (np.where(all_shifts['name']== "ALEXIS LAFRENI?RE" , "ALEXIS LAFRENIÈRE",
    (np.where(all_shifts['name']== "ALEXIS LAFRENIERE" , "ALEXIS LAFRENIÈRE", 
    (np.where(all_shifts['name']== "ALEXIS LAFRENIÃRE" , "ALEXIS LAFRENIÈRE",
    (np.where(all_shifts['name']== "JANI HAKANPÃ\x84Ã\x84" , "JANI HAKANPAA",
    (np.where(all_shifts['name']== "TIM STUTZLE" , "TIM STÜTZLE",
    (np.where(all_shifts['name']== "TIM ST?TZLE" , "TIM STÜTZLE",
    (np.where(all_shifts['name']== "TIM STÃTZLE" , "TIM STÜTZLE",
    (np.where(all_shifts['name']== "EGOR SHARANGOVICH" , "YEGOR SHARANGOVICH",
    (np.where(all_shifts['name']== "CALLAN FOOTE" , "CAL FOOTE",
    (np.where(all_shifts['name']== "MATTIAS JANMARK-NYLEN" , "MATTIAS JANMARK",
    (np.where(all_shifts['name']== 'ALEX BARRÃ-BOULET', 'ALEX BARRE-BOULET',
    (np.where(all_shifts['name']== "JOSH DUNNE" , "JOSHUA DUNNE",all_shifts['name'])))))))))))))))))))))))))))))))))))))))))))
    )))))))))))))))))))))))))))))))))))))

    all_shifts['name'] = all_shifts['name'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.upper()
    
    
    all_shifts = all_shifts.assign(end_time = np.where(pd.to_datetime(all_shifts.start_time).dt.time > pd.to_datetime(all_shifts.end_time).dt.time, '20:00', all_shifts.end_time),
                                  goalie = np.where(all_shifts.name.isin(goalie_names), 1, 0))
    
    all_shifts = all_shifts.merge(all_shifts.groupby(['team', 'period'])['goalie'].sum().reset_index().rename(columns = {'goalie':'period_gs'}))
    
    # Implement fix for goalies: Goalies who showed up late in the period and were the only goalie to play have their start time re-set to 0:00. 
    
    all_shifts = all_shifts.assign(start_time = np.where((all_shifts.goalie==1) & (all_shifts.start_time!='0:00') & (all_shifts.period_gs==1), '0:00', all_shifts.start_time))
    
    all_shifts = all_shifts.assign(end_time = np.where(
    (pd.to_datetime(all_shifts.start_time).dt.time < datetime(2021, 6, 10, 18, 0, 0).time()) & 
    (all_shifts.period!=3) & 
    (all_shifts.period!=4) &
    (all_shifts.period!=5) &
    (all_shifts.goalie==1) &
    (all_shifts.period_gs==1),
    '20:00', all_shifts.end_time))
    
    all_shifts = all_shifts.assign(end_time = np.where(
    (pd.to_datetime(all_shifts.start_time).dt.time < datetime(2021, 6, 10, 13, 0, 0).time()) & 
    (all_shifts.period!=4) &
    (all_shifts.period!=5) &
    (all_shifts.goalie==1) &
    (all_shifts.period_gs==1),
    '20:00', all_shifts.end_time))
    
    global myshifts
    global changes_on
    global changes_off
    myshifts = all_shifts
    
    myshifts.start_time = myshifts.start_time.str.strip()
    myshifts.end_time = myshifts.end_time.str.strip()

    changes_on = myshifts.groupby(['team', 'period', 'start_time']).agg(
        on = ('name', ', '.join),
        on_numbers = ('number', ', '.join),
        number_on = ('name', 'count')
    ).reset_index().rename(columns = {'start_time':'time'}).sort_values(by = ['team', 'period', 'time'])
    
    changes_off = myshifts.groupby(['team', 'period', 'end_time']).agg(
        off = ('name', ', '.join),
        off_numbers = ('number', ', '.join),
        number_off = ('name', 'count')
    ).reset_index().rename(columns = {'end_time':'time'}).sort_values(by = ['team', 'period', 'time'])
    
    all_on = changes_on.merge(changes_off, on = ['team', 'period', 'time'], how = 'left')
    off_only = changes_off.merge(changes_on, on = ['team', 'period', 'time'], how = 'left', indicator = True)[
    changes_off.merge(changes_on, on = ['team', 'period', 'time'], how = 'left', indicator = True)['_merge']!='both']
    full_changes = pd.concat([all_on, off_only]).sort_values(by = ['period', 'time']).drop(columns = ['_merge'])
    
    full_changes['period_seconds'] = full_changes.time.str.split(':').str[0].astype(int) * 60 + full_changes.time.str.split(':').str[1].astype(int)

    full_changes['game_seconds'] = (np.where((full_changes.period<5) & int(game_id[0])!=3, 
                                   (((full_changes.period - 1) * 1200) + full_changes.period_seconds),
                          3900))
    
    full_changes = full_changes.assign(team = np.where(full_changes.team=='CANADIENS MONTREAL', 'MONTREAL CANADIENS', full_changes.team))
        
    return full_changes.reset_index(drop = True)#.drop(columns = ['time', 'period_seconds']) 

def scrape_api_events(game_id, drop_description = True, shift_to_espn = False):
    
    if shift_to_espn == True:
        raise KeyError
    
    page = requests.get(str('https://api-web.nhle.com/v1/gamecenter/' + str(game_id) + '/play-by-play'))
    
    if str(page) == '<Response [404]>':
        raise KeyError('You got the 404 error; game data could not be found.')
    
    loaddict = json.loads(page.content)
    
    if loaddict['liveData']['plays']['allPlays'] != []:
    
        eventdf = pd.DataFrame(loaddict['liveData']['plays']['allPlays'])

        coordsdf = pd.DataFrame(eventdf['coordinates'].values.tolist(), index = eventdf.index)
        resultdf = pd.DataFrame(eventdf['result'].values.tolist(), index = eventdf.index)
        aboutdf = pd.DataFrame(eventdf['about'].values.tolist(), index = eventdf.index)
        scoredf = pd.DataFrame(aboutdf['goals'].values.tolist(), index = aboutdf.index)
        playerdf = pd.DataFrame(eventdf['players'])
        teamdf = eventdf['team'].apply(pd.Series)
        clean = playerdf[~pd.isna(playerdf.players)].reset_index()
        clean_index = clean.loc[:, ['index']]
        player1 = pd.DataFrame((pd.DataFrame(clean.reset_index()['players'].values.tolist())[0].values.tolist()))
        player1df = pd.concat([clean_index, pd.DataFrame(player1['player'].values.tolist())], axis = 1).assign(playerType = player1['playerType']).rename(
            columns = {'id':'player1id', 'fullName':'player1name', 'link':'player1link', 'playerType':'player1type'})
        player2 = pd.concat([clean_index, pd.DataFrame((pd.DataFrame(clean['players'].values.tolist())[1]))], axis = 1)
        player2 = player2[player2[1].notnull()]
        player2df = pd.concat([player2.reset_index(drop = True), 
            (pd.DataFrame(pd.DataFrame(player2[1].values.tolist())['player'].values.tolist()).assign(playerType = (pd.DataFrame(player2[1].values.tolist())).loc[:, ['playerType']]))], axis = 1).drop(
        columns = 1).rename(
            columns = {'id':'player2id', 'fullName':'player2name', 'link':'player2link', 'playerType':'player2type'})

        if len((pd.DataFrame(clean['players'].values.tolist())).columns) > 2:

            player3 = pd.concat([clean_index, pd.DataFrame((pd.DataFrame(clean['players'].values.tolist())[2]))], axis = 1)
            player3 = player3[player3[2].notnull()]
            player3df = pd.concat([player3.reset_index(drop = True), 
                (pd.DataFrame(pd.DataFrame(player3[2].values.tolist())['player'].values.tolist()).assign(playerType = (pd.DataFrame(player3[2].values.tolist())).loc[:, ['playerType']]))], axis = 1).drop(
            columns = 2).rename(
                columns = {'id':'player3id', 'fullName':'player3name', 'link':'player3link', 'playerType':'player3type'})
        else: 
            player3df = pd.DataFrame(columns = ['index', 'player3id', 'player3name', 'player3link', 'player3type'])

        if len((pd.DataFrame(clean['players'].values.tolist())).columns) > 3:  

            player4 = pd.concat([clean_index, pd.DataFrame((pd.DataFrame(clean['players'].values.tolist())[3]))], axis = 1)
            player4 = player4[player4[3].notnull()]
            player4df = pd.concat([player4.reset_index(drop = True), 
                (pd.DataFrame(pd.DataFrame(player4[3].values.tolist())['player'].values.tolist()).assign(playerType = (pd.DataFrame(player4[3].values.tolist())).loc[:, ['playerType']]))], axis = 1).drop(
            columns = 3).rename(
                columns = {'id':'player4id', 'fullName':'player4name', 'link':'player4link', 'playerType':'player4type'})
        else: 
            player4df = pd.DataFrame(columns = ['index', 'player4id', 'player4name', 'player4link', 'player4type'])

        finaldf = eventdf.assign(
            hometeam = loaddict['gameData']['teams']['home']['triCode'],
            hometeamfull = loaddict['gameData']['teams']['home']['name'],
            awayteam = loaddict['gameData']['teams']['away']['triCode'],
            awayteamfull = loaddict['gameData']['teams']['away']['name'],
            description = resultdf['description'],
            event = resultdf['eventTypeId'],
            detail = resultdf['secondaryType'],
            coords_x = coordsdf['x'],
            coords_y = coordsdf['y'],
            period = aboutdf['period'],
            time = aboutdf['periodTime'],
            homescore = scoredf['home'],
            awayscore = scoredf['away'],
            eventteam = teamdf['triCode'],
            eventteamfull = teamdf['name'],
            eventidx = aboutdf['eventIdx'],
            eventNumber = aboutdf['eventId'],
            session = loaddict['gameData']['game']['type'])

        finaldf = finaldf.drop(columns = ['result', 'about', 'coordinates', 'players', 'team'])

        finaldf = finaldf.reset_index().merge(
        player1df, on = 'index', how = 'left').merge(
        player2df, on = 'index', how = 'left').merge(
        player3df, on = 'index', how = 'left').merge(
        player4df, on = 'index', how = 'left')
        
        finaldf = finaldf.assign(
            awayteamfull = finaldf.awayteamfull.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8'),
            hometeamfull = finaldf.hometeamfull.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8'),
            eventteamfull = finaldf.eventteamfull.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8'))
        
        finaldf = finaldf.assign(
            player1name = np.where((finaldf.player1name=='Sebastian Aho') & (finaldf.eventteam=='NYI'),
                     'Sebastian Aho (SWE)',
                     finaldf.player1name
                    ))

        api_events = finaldf
    
        api_events.period = api_events.period.astype(int)
        api_events.time = api_events.time.astype(str)

        api_events.event = np.where(api_events.event=='BLOCKED_SHOT', 'BLOCK',
        np.where(api_events.event=='BLOCKEDSHOT', 'BLOCK',
                np.where(api_events.event=='MISSED_SHOT', 'MISS',
                        np.where(api_events.event=='FACEOFF', 'FAC',
                                np.where(api_events.event=='PENALTY', 'PENL',
                                        np.where(api_events.event=='GIVEAWAY', 'GIVE',
                                                np.where(api_events.event=='TAKEAWAY', 'TAKE',
                                                         np.where(api_events.event=='MISSEDSHOT', 'MISS',
                                                                  api_events.event))))))))

        api_events = api_events[api_events.event.isin(['TAKE', 'GIVE', 'MISS', 'HIT', 'SHOT', 'BLOCK', 'GOAL', 'PENL', 'FAC'])]

        api_events['awayteamfull'] = (api_events.awayteamfull.str.upper())
        api_events['hometeamfull'] = (api_events.hometeamfull.str.upper())
        api_events['eventteamfull'] = (api_events.eventteamfull.str.upper())

        api_events['period_seconds'] = api_events.time.str.split(':').str[0].astype(int) * 60 + api_events.time.str.split(':').str[1].astype(int)

        api_events['game_seconds'] = (np.where(api_events.period<5, 
                                       (((api_events.period - 1) * 1200) + api_events.period_seconds),
                              3900))


        api_events = api_events.loc[:, ['period_seconds', 'game_seconds', 'event', 'session', 'coords_x', 'coords_y', 'description', 'period',
                                        'eventteam', 'eventteamfull', 'hometeamfull', 'awayteamfull', 'player1name', 'player2name', 'player3name', 'player4name']].rename(
            columns = {'eventteamfull':'event_team'})

        api_events = api_events.assign(
        player1name = api_events.player1name.str.upper(),
        player2name = api_events.player2name.str.upper(),
        player3name = api_events.player3name.str.upper()
        ).drop(columns = 'player4name').rename(columns = {'player1name':'ep1_name', 'player2name':'ep2_name', 'player3name':'ep3_name'})
    
        api_events = api_events.assign(event_team = np.where(api_events.event!='BLOCK', api_events.event_team,
            np.where(api_events.event_team==api_events.hometeamfull, api_events.awayteamfull, api_events.hometeamfull)))
        
        api_events = api_events.assign(ep1_name = np.where(api_events.event!='BLOCK', api_events.ep1_name, api_events.ep2_name))
    
        api_events = api_events.sort_values(by = ['game_seconds', 'event_team', 'ep1_name'])
    
        api_events = api_events.assign(version = 
                               (np.where(
                               (api_events.event==api_events.event.shift()) & 
                               (api_events.ep1_name==api_events.ep1_name.shift()) &
                               (api_events.game_seconds==api_events.game_seconds.shift()),
                                1, 0)))

        api_events = api_events.assign(version = 
                               (np.where(
                               (api_events.event==api_events.event.shift(2)) & 
                               (api_events.ep1_name==api_events.ep1_name.shift(2)) &
                               (api_events.game_seconds==api_events.game_seconds.shift(2) )& 
                               (~api_events.description.str.contains('Penalty Shot')),
                                2, api_events.version)))

        api_events = api_events.assign(version = 
                               (np.where(
                               (api_events.event==api_events.event.shift(3)) & 
                               (api_events.ep1_name==api_events.ep1_name.shift(3)) &
                               (api_events.game_seconds==api_events.game_seconds.shift(3)),
                                3, api_events.version)))#.drop(columns = 'description')
        
        api_events['ep1_name'] = np.where((api_events.description.str.contains('Too many men')) | (api_events.description.str.contains('unsportsmanlike conduct-bench')), 'BENCH', api_events['ep1_name'])
        
        api_events['ep1_name'] = np.where(api_events['ep1_name'].str.contains('ALEXANDRE '), 
                                api_events['ep1_name'].str.replace('ALEXANDRE ', 'ALEX '),
                                api_events['ep1_name'])
    
        api_events['ep1_name'] = np.where(api_events['ep1_name'].str.contains('ALEXANDER '), 
                                    api_events['ep1_name'].str.replace('ALEXANDER ', 'ALEX '),
                                    api_events['ep1_name'])

        api_events['ep1_name'] = np.where(api_events['ep1_name'].str.contains('CHRISTOPHER '), 
                                    api_events['ep1_name'].str.replace('CHRISTOPHER ', 'CHRIS '),
                                    api_events['ep1_name'])
        
        api_events = api_events.assign(
        ep1_name = 
        (np.where(api_events['ep1_name']=="ALEX PECHURSKIY", "ALEX PECHURSKI", 
        (np.where(api_events['ep1_name']=="BEN ONDRUS", "BENJAMIN ONDRUS", 
        (np.where(api_events['ep1_name']=="BRYCE VAN BRABANT", "BRYCE VAN BRABANT", 
        (np.where(api_events['ep1_name']=="CALVIN DE HAAN", "CALVIN DE HAAN", 
        (np.where(api_events['ep1_name']=="CHASE DE LEO", "CHASE DE LEO", 
        (np.where(api_events['ep1_name']=="CAL PETERSEN", "CALVIN PETERSEN",
        (np.where(api_events['ep1_name']=="DANIEL CARCILLO", "DAN CARCILLO", 
        (np.where(api_events['ep1_name']=="DANNY O'REGAN", "DANIEL O'REGAN", 
        (np.where(api_events['ep1_name']=="DAVID VAN DER GULIK", "DAVID VAN DER GULIK", 
        (np.where(api_events['ep1_name']=="EVGENII DADONOV", "EVGENY DADONOV", 
        (np.where(api_events['ep1_name']=="FREDDY MODIN", "FREDRIK MODIN", 
        (np.where(api_events['ep1_name']=="GREG DE VRIES", "GREG DE VRIES", 
        (np.where(api_events['ep1_name']=="ILYA ZUBOV", "ILJA ZUBOV", 
        (np.where(api_events['ep1_name']=="JACOB DE LA ROSE", "JACOB DE LA ROSE", 
        (np.where(api_events['ep1_name']=="JAMES VAN RIEMSDYK", "JAMES VAN RIEMSDYK", 
        (np.where(api_events['ep1_name']=="JEAN-FRANCOIS JACQUES", "J-F JACQUES", 
        (np.where(api_events['ep1_name']=="JAKOB FORSBACKA KARLSSON", "JAKOB FORSBACKA KARLSSON", 
        (np.where(api_events['ep1_name']=="JIM DOWD", "JAMES DOWD", 
        (np.where(api_events['ep1_name']=="JEFF HAMILTON", "JEFFREY HAMILTON", 
        (np.where(api_events['ep1_name']=="JEFF PENNER", "JEFFREY PENNER", 
        (np.where(api_events['ep1_name']=="JOEL ERIKSSON EK", "JOEL ERIKSSON EK", 
        (np.where(api_events['ep1_name']=="MARK VAN GUILDER", "MARK VAN GUILDER", 
        (np.where(api_events['ep1_name']=="MARTIN ST LOUIS", "MARTIN ST. LOUIS", 
        (np.where(api_events['ep1_name']=="MARTIN ST PIERRE", "MARTIN ST. PIERRE", 
        (np.where(api_events['ep1_name']=="MARTIN ST PIERRE", "MARTIN ST. PIERRE", 
        (np.where(api_events['ep1_name']=="MICHAEL CAMMALLERI", "MIKE CAMMALLERI", 
        (np.where(api_events['ep1_name']=="MICHAEL DAL COLLE", "MICHAEL DAL COLLE", 
        (np.where(api_events['ep1_name']=="MICHAEL DEL ZOTTO", "MICHAEL DEL ZOTTO", 
        (np.where(api_events['ep1_name']=="MIKE VERNACE", "MICHAEL VERNACE", 
        (np.where(api_events['ep1_name']=="MIKE YORK", "MICHAEL YORK", 
        (np.where(api_events['ep1_name']=="MIKE VAN RYN", "MIKE VAN RYN", 
        (np.where(api_events['ep1_name']=="MITCHELL MARNER", "MITCH MARNER", 
        (np.where(api_events['ep1_name']=="PAT MAROON", "PATRICK MAROON", 
        (np.where(api_events['ep1_name']=="PA PARENTEAU", "P.A. PARENTEAU", 
        (np.where(api_events['ep1_name']=="PHILLIP DI GIUSEPPE", "PHILLIP DI GIUSEPPE", 
        (np.where(api_events['ep1_name']=="STEFAN DELLA ROVERE", "STEFAN DELLA ROVERE", 
        (np.where(api_events['ep1_name']=="STEPHANE DA COSTA", "STEPHANE DA COSTA", 
        (np.where(api_events['ep1_name']=="TJ GALIARDI", "T.J. GALIARDI", 
        (np.where(api_events['ep1_name']=="TOBY ENSTROM", "TOBIAS ENSTROM",  
        (np.where(api_events['ep1_name']=="TREVOR VAN RIEMSDYK", "TREVOR VAN RIEMSDYK", 
        (np.where(api_events['ep1_name']=="ZACK FITZGERALD", "ZACH FITZGERALD", 

        ## NEW CHANGES
        (np.where(api_events['ep1_name']=="TIM GETTINGER", "TIMOTHY GETTINGER", 
        (np.where(api_events['ep1_name']=="THOMAS DI PAULI", "THOMAS DI PAULI", 
        (np.where(api_events['ep1_name']=="NICHOLAS SHORE", "NICK SHORE",
        (np.where(api_events['ep1_name']=="T.J. TYNAN", "TJ TYNAN",

        ## '20-21 CHANGES (from HTM update function)
        (np.where(api_events['ep1_name']=="ALEXIS LAFRENI?RE", "ALEXIS LAFRENIÈRE",
        (np.where(api_events['ep1_name']=="ALEXIS LAFRENIERE", "ALEXIS LAFRENIÈRE",
        (np.where(api_events['ep1_name']=="TIM STUTZLE", "TIM STÜTZLE",
        (np.where(api_events['ep1_name']=="TIM ST?TZLE", "TIM STÜTZLE",
        (np.where(api_events['ep1_name']== "JANI HAKANPÃ\x84Ã\x84" , "JANI HAKANPAA",
        (np.where(api_events['ep1_name']=="EGOR SHARANGOVICH", "YEGOR SHARANGOVICH",
        (np.where(api_events['ep1_name']=="CALLAN FOOTE", "CAL FOOTE",
        (np.where(api_events['ep1_name']=="JOSH DUNNE", "JOSHUA DUNNE", api_events['ep1_name']
        ))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))
        )))))))))))))))))))))))))))))))))))))))))))))))

        # 21-22 CHANGES

        api_events['ep1_name'] = api_events['ep1_name'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.upper()

        api_events = api_events.assign(ep1_name = np.where(api_events.ep1_name=='ALEX BARRÃ-BOULET', 'ALEX BARRE_BOULET', api_events.ep1_name))

        if drop_description == True:
        
            return api_events.loc[:, ['game_seconds', 'event', 'coords_x', 'coords_y', 'ep1_name', 'period', 'version']].rename(columns = {'ep1_name':'event_player_1'})
        
        else:
            
            return api_events.loc[:, ['game_seconds', 'event', 'coords_x', 'coords_y', 'ep1_name', 'period', 'version', 'description']].rename(columns = {'ep1_name':'event_player_1'})
        
    else:
        print("This game doesn't exist within the API.")
        raise KeyError

def scrape_html_events(season, game_id):
    #global game
    url = 'http://www.nhl.com/scores/htmlreports/' + season + '/PL0' + game_id + '.HTM'
    page = requests.get(url)
    #if int(season)<20092010:
     #   soup = BeautifulSoup(page.content, 'html.parser')
    #else:
     #   soup = BeautifulSoup(page.content, 'lxml')
    soup = BeautifulSoup(page.content.decode('ISO-8859-1'), 'lxml')
    tds = soup.find_all("td", {"class": re.compile('.*bborder.*')})
    #global stripped_html
    #global eventdf
    stripped_html = hs_strip_html(tds)
    length = int(len(stripped_html)/8)
    eventdf = pd.DataFrame(np.array(stripped_html).reshape(length, 8)).rename(
    columns = {0:'index', 1:'period', 2:'strength', 3:'time', 4:'event', 5:'description', 6:'away_skaters', 7:'home_skaters'})
    split = eventdf.time.str.split(':')
    game_date = soup.find_all('td', {'align':'center', 'style':'font-size: 10px;font-weight:bold'})[2].get_text()
    
    potentialnames = soup.find_all('td', {'align':'center', 'style':'font-size: 10px;font-weight:bold'})
    
    for i in range(0, 999):
        away = potentialnames[i].get_text()
        if ('Away Game') in away or ('tr./Away') in away:
            away = re.split('Match|Game', away)[0]
            break
        
    for i in range(0, 999):
        home = potentialnames[i].get_text()
        if ('Home Game') in home or ('Dom./Home') in home:
            home = re.split('Match|Game', home)[0]
            break
            
    game = eventdf.assign(away_skaters = eventdf.away_skaters.str.replace('\n', ''),
                  home_skaters = eventdf.home_skaters.str.replace('\n', ''),
                  original_time = eventdf.time,
                  time = split.str[0] + ":" + split.str[1].str[:2],
                  home_team = home,
                  away_team = away)
    
    game = game.assign(away_team_abbreviated = game.away_skaters[0].split(' ')[0],
                       home_team_abbreviated = game.home_skaters[0].split(' ')[0])
    
    game = game[game.period!='Per']
    
    game = game.assign(index = game.index.astype(int)).rename(columns = {'index':'event_index'})
    
    game = game.assign(event_team = game.description.str.split(' ').str[0])
    
    game = game.assign(event_team = game.event_team.str.split('\xa0').str[0])
    
    game = game.assign(event_team = np.where(~game.event_team.isin([game.home_team_abbreviated.iloc[0], game.away_team_abbreviated.iloc[0]]), '\xa0', game.event_team))
    
    game = game.assign(other_team = np.where(game.event_team=='', '\xa0',
                                            np.where(game.event_team==game.home_team_abbreviated.iloc[0], game.away_team_abbreviated.iloc[0], game.home_team_abbreviated.iloc[0])))
    
    game['event_player_str'] = game.description.apply(
    lambda x: re.findall('(#)(\d\d)|(#)(\d)|(-) (\d\d)|(-) (\d)', x)).astype(str
                                                        ).str.replace('#', '').str.replace('-', '').str.replace("'", '').str.replace(',', '').str.replace('(', '').str.replace(')', '').astype(str
                                                        ).str.replace('[', '').str.replace(']', '').apply(lambda x: re.sub(' +', ' ', x)).str.strip()

    game = game.assign(event_player_1 = 
            game.event_player_str.str.split(' ').str[0],
            event_player_2 = 
            game.event_player_str.str.split(' ').str[1],
            event_player_3 = 
            game.event_player_str.str.split(' ').str[2])
    #return game

    if len(game[game.description.str.contains('Drawn By')])>0:
    
        game = game.assign(event_player_2 = np.where(game.description.str.contains('Drawn By'), 
                                          game.description.str.split('Drawn By').str[1].str.split('#').str[1].str.split(' ').str[0].str.strip(), 
                                          game.event_player_2),
                          event_player_3 = np.where(game.description.str.contains('Served By'),
                                                   '\xa0',
                                                   game.event_player_3))

    game = game.assign(event_player_1 = np.where((~pd.isna(game.event_player_1)) & (game.event_player_1!=''),
                              np.where(game.event=='FAC', game.away_team_abbreviated,
                                       game.event_team) + (game.event_player_1.astype(str)), 
                              game.event_player_1),
                  event_player_2 = np.where((~pd.isna(game.event_player_2)) & (game.event_player_2!=''),
                              np.where(game.event=='FAC', game.home_team_abbreviated,
                                       np.where(game.event.isin(['BLOCK', 'HIT', 'PENL']), game.other_team, game.event_team)) + (game.event_player_2.astype(str)), 
                              game.event_player_2),
                  event_player_3 = np.where((~pd.isna(game.event_player_3)) & (game.event_player_3!=''),
                              game.event_team + (game.event_player_3.astype(str)), 
                              game.event_player_3))
    
    game = game.assign(
        event_player_1 = np.where((game.event=='FAC') & (game.event_team==game.home_team_abbreviated),
                                 game.event_player_2, game.event_player_1),
        event_player_2 = np.where((game.event=='FAC') & (game.event_team==game.home_team_abbreviated),
                                 game.event_player_1, game.event_player_2))
    
    #return game
    
    roster = scrape_html_roster(season, game_id).rename(columns = {'Nom/Name':'Name'})
    roster = roster[roster.status=='player']
    roster = roster.assign(team_abbreviated = np.where(roster.team=='home', 
                                                       game.home_team_abbreviated.iloc[0],
                                                      game.away_team_abbreviated.iloc[0]))

    roster = roster.assign(teamnum = roster.team_abbreviated + roster['#'],
                          Name = roster.Name.str.split('(').str[0].str.strip())
    
    event_player_1s = roster.loc[:, ['teamnum', 'Name']].rename(columns = {'teamnum':'event_player_1', 'Name':'ep1_name'})
    event_player_2s = roster.loc[:, ['teamnum', 'Name']].rename(columns = {'teamnum':'event_player_2', 'Name':'ep2_name'})
    event_player_3s = roster.loc[:, ['teamnum', 'Name']].rename(columns = {'teamnum':'event_player_3', 'Name':'ep3_name'})
    
    game = game.merge(
    event_player_1s, on = 'event_player_1', how = 'left').merge(
    event_player_2s, on = 'event_player_2', how = 'left').merge(
    event_player_3s, on = 'event_player_3', how = 'left').assign(
    date = game_date)
    #return game
    game['period'] = np.where(game['period'] == '', '1', game['period'])
    game['time'] = np.where((game['time'] == '') | (pd.isna(game['time'])), '0:00', game['time'])
    game['period'] = game.period.astype(int)

    game['period_seconds'] = game.time.str.split(':').str[0].str.replace('-', '').astype(int) * 60 + game.time.str.split(':').str[1].str.replace('-', '').astype(int)

    game['game_seconds'] = (np.where((game.period<5) & int(game_id[0])!=3, 
                                       (((game.period - 1) * 1200) + game.period_seconds),
                              3900))
    
    game = game.assign(priority = np.where(game.event.isin(['TAKE', 'GIVE', 'MISS', 'HIT', 'SHOT', 'BLOCK']), 1, 
                                            np.where(game.event=="GOAL", 2,
                                                np.where(game.event=="STOP", 3,
                                                    np.where(game.event=="DELPEN", 4,
                                                        np.where(game.event=="PENL", 5,
                                                            np.where(game.event=="CHANGE", 6,
                                                                np.where(game.event=="PEND", 7,
                                                                    np.where(game.event=="GEND", 8,
                                                                        np.where(game.event=="FAC", 9, 0)))))))))).sort_values(by = ['game_seconds', 'period', 'event_player_1', 'event'])
    game = game.assign(version = 
                       (np.where(
                       (game.event==game.event.shift()) & 
                       (game.event_player_1==game.event_player_1.shift()) &
                       (game.event_player_1!='') &
                       (game.game_seconds==game.game_seconds.shift()),
                        1, 0)))
    
    game = game.assign(version = 
                           (np.where(
                           (game.event==game.event.shift(2)) & 
                           (game.event_player_1==game.event_player_1.shift(2)) &
                           (game.game_seconds==game.game_seconds.shift(2)) & 
                           (game.event_player_1!='') &
                           (~game.description.str.contains('Penalty Shot')),
                            2, game.version)))
    
    game = game.assign(version = 
                           (np.where(
                           (game.event==game.event.shift(3)) & 
                           (game.event_player_1==game.event_player_1.shift(3)) &
                           (game.game_seconds==game.game_seconds.shift(3)) & 
                           (game.event_player_1!=''),
                            3, game.version)))
    
    game = game.assign(date = pd.to_datetime(game.date[~pd.isna(game.date)].iloc[0])
                  ).rename(columns = {'date':'game_date'}).sort_values(by = ['event_index'])
    
    game = game.assign(event_player_1 = game.ep1_name, event_player_2 = game.ep2_name, event_player_3 = game.ep3_name).drop(columns = ['ep1_name', 'ep2_name', 'ep3_name'])
    
    game = game.assign(home_team = np.where(game.home_team=='CANADIENS MONTREAL', 'MONTREAL CANADIENS', game.home_team),
                      away_team = np.where(game.away_team=='CANADIENS MONTREAL', 'MONTREAL CANADIENS', game.away_team))
    
    if int(game_id[0])!=3:
        game = game[game.game_seconds<4000]
    
    game['game_date'] = np.where((season=='20072008') & (game_id == '20003'), game.game_date + pd.Timedelta(days=1), game.game_date)
    
    game = game.assign(event_player_1 = np.where((game.description.str.upper().str.contains('TEAM')) | (game.description.str.lower().str.contains('bench')),
                                     'BENCH',
                                     game.event_player_1))
    
    game = game.assign(home_skater_count_temp = (game.home_skaters.apply(lambda x: len(re.findall('[A-Z]', x)))),
          away_skater_count_temp = (game.away_skaters.apply(lambda x: len(re.findall('[A-Z]', x))))
         )
    
    game = game.assign(event_team = np.where((game.event=='PENL') & (game.event_team=='') & (game.description.str.lower().str.contains('bench')) & (game.home_skater_count_temp>game.home_skater_count_temp.shift(-1)),
                                game.home_team_abbreviated, game.event_team))

    game = game.assign(event_team = np.where((game.event=='PENL') & (game.event_team=='') & (game.description.str.lower().str.contains('bench')) & (game.away_skater_count_temp>game.away_skater_count_temp.shift(-1)),
                                game.away_team_abbreviated, game.event_team))
    
    return game.drop(columns = ['period_seconds', 'time', 'priority', 'home_skater_count_temp', 'away_skater_count_temp'])

def scrape_espn_events(espn_game_id, drop_description = True):

    # This URL has event coordinates
    
    url = f'https://www.espn.com/nhl/playbyplay/_/gameId/{espn_game_id}'
    
    page = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout = 500)
    
    soup = BeautifulSoup(page.content.decode('ISO-8859-1'), 'lxml', multi_valued_attributes = None)
    
    period_jsons = json.loads(str(soup).split('"playGrps":')[1].split(',"tms"')[0])
    
    clock_df = pd.DataFrame()

    for period in range(0, len(period_jsons)):
        clock_df = clock_df._append(pd.DataFrame(period_jsons[period]))

    clock_df = clock_df[~pd.isna(clock_df.clock)]

    # Needed to add .split(',"st":3')[0] for playoffs

    coords_df = pd.DataFrame(json.loads(str(soup).split('plays":')[1].split(',"st":1')[0].split(',"st":2')[0].split(',"st":3')[0]))

    clock_df = clock_df.assign(
        clock = clock_df.clock.apply(lambda x: x['displayValue'])
    )
    
    coords_df = coords_df.assign(
        coords_x = coords_df[~pd.isna(coords_df.coordinate)].coordinate.apply(lambda x: x['x']).astype(int),
        coords_y = coords_df[~pd.isna(coords_df.coordinate)].coordinate.apply(lambda y: y['y']).astype(int),
        event_player_1 = coords_df[~pd.isna(coords_df.athlete)]['athlete'].apply(lambda x: x['name'])
    )

    espn_events = coords_df.merge(clock_df.loc[:, ['id', 'clock']])

    espn_events = espn_events.assign(
        period = espn_events['period'].apply(lambda x: x['number']),
        minutes = espn_events['clock'].str.split(':').apply(lambda x: x[0]).astype(int),
        seconds = espn_events['clock'].str.split(':').apply(lambda x: x[1]).astype(int),
        event_type = espn_events['type'].apply(lambda x: x['txt'])
    )

    espn_events = espn_events.assign(coords_x = np.where((pd.isna(espn_events.coords_x)) & (pd.isna(espn_events.coords_y)) &
                (espn_events.event_type=='Face Off'), 0, espn_events.coords_x
    ),
                      coords_y = np.where((pd.isna(espn_events.coords_x)) & (pd.isna(espn_events.coords_y)) &
                (espn_events.event_type=='Face Off'), 0, espn_events.coords_y))

    espn_events = espn_events[(~pd.isna(espn_events.coords_x)) & (~pd.isna(espn_events.coords_y)) & (~pd.isna(espn_events.event_player_1))]

    espn_events = espn_events.assign(
        # Do this later
        coords_x = espn_events.coords_x.astype(int),
        coords_y = espn_events.coords_y.astype(int)
    )
    
    espn_events = espn_events.rename(columns = {'text':'description'})
    
    espn_events = espn_events.assign(
        event_type = np.where(espn_events.event_type=='Face Off', 'FAC',
                             np.where(espn_events.event_type=='Goal', 'GOAL',
                                 np.where(espn_events.event_type=='Giveaway', 'GIVE',
                                     np.where(espn_events.event_type=='Penalty', 'PENL',
                                         np.where(espn_events.event_type=='Missed', 'MISS',
                                             np.where(espn_events.event_type=='Shot', 'SHOT',
                                                 np.where(espn_events.event_type=='Takeaway', 'TAKE',
                                                     np.where(espn_events.event_type=='Blocked', 'BLOCK',
                                                         np.where(espn_events.event_type=='Hit', 'HIT',
                                                              espn_events.event_type))))))))))
    
    espn_events = espn_events.assign(priority = np.where(espn_events.event_type.isin(['TAKE', 'GIVE', 'MISS', 'HIT', 'SHOT', 'BLOCK']), 1, 
                                            np.where(espn_events.event_type=="GOAL", 2,
                                                np.where(espn_events.event_type=="STOP", 3,
                                                    np.where(espn_events.event_type=="DELPEN", 4,
                                                        np.where(espn_events.event_type=="PENL", 5,
                                                            np.where(espn_events.event_type=="CHANGE", 6,
                                                                np.where(espn_events.event_type=="PEND", 7,
                                                                    np.where(espn_events.event_type=="GEND", 8,
                                                                        np.where(espn_events.event_type=="FAC", 9, 0))))))))),
                                    event_player_1 = espn_events.event_player_1.str.upper(),
                                    game_seconds = np.where(espn_events.period<5, 
                                    ((espn_events.period - 1) * 1200) + (espn_events.minutes * 60) + espn_events.seconds, 3900))
    
    espn_events = espn_events.sort_values(by = ['period', 'game_seconds', 'event_player_1', 'priority']).rename(
    columns = {'event_type':'event'}).loc[:, ['coords_x', 'coords_y', 'event_player_1', 'event', 'game_seconds', 'description', 'period']]
    
    espn_events['event_player_1'] = np.where(espn_events['event_player_1'].str.contains('ALEXANDRE '), 
                                espn_events['event_player_1'].str.replace('ALEXANDRE ', 'ALEX '),
                                espn_events['event_player_1'])
    
    espn_events['event_player_1'] = np.where(espn_events['event_player_1'].str.contains('ALEXANDER '), 
                                espn_events['event_player_1'].str.replace('ALEXANDER ', 'ALEX '),
                                espn_events['event_player_1'])
    
    espn_events['event_player_1'] = np.where(espn_events['event_player_1'].str.contains('CHRISTOPHER '), 
                                espn_events['event_player_1'].str.replace('CHRISTOPHER ', 'CHRIS '),
                                espn_events['event_player_1'])
    
    espn_events = espn_events.assign(event_player_1 = 
    np.where(espn_events.event_player_1=='PATRICK MAROON', 'PAT MAROON',
    (np.where(espn_events.event_player_1=='J T COMPHER', 'J.T. COMPHER', 
    (np.where(espn_events.event_player_1=='J T MILLER', 'J.T. MILLER', 
    (np.where(espn_events.event_player_1=='T J OSHIE', 'T.J. OSHIE', 
    (np.where((espn_events.event_player_1=='ALEXIS LAFRENIERE') | (espn_events.event_player_1=='ALEXIS LAFRENI RE'), 'ALEXIS LAFRENIÈRE', 
    (np.where((espn_events.event_player_1=='TIM STUTZLE') | (espn_events.event_player_1=='TIM ST TZLE'), 'TIM STÜTZLE',
    (np.where(espn_events.event_player_1=='T.J. BRODIE', 'TJ BRODIE',
    (np.where(espn_events.event_player_1=='MATTHEW IRWIN', 'MATT IRWIN',
    (np.where(espn_events.event_player_1=='STEVE KAMPFER', 'STEVEN KAMPFER',
    (np.where(espn_events.event_player_1=='STEVE KAMPFER', 'STEVEN KAMPFER',
    (np.where(espn_events.event_player_1=='JEFFREY TRUCHON-VIEL', 'JEFFREY VIEL',
    (np.where(espn_events.event_player_1=='ZACHARY JONES', 'ZAC JONES',
    (np.where(espn_events.event_player_1=='MITCH MARNER', 'MITCHELL MARNER',
    (np.where(espn_events.event_player_1=='MATHEW DUMBA', 'MATT DUMBA',
    (np.where(espn_events.event_player_1=='JOSHUA MORRISSEY', 'JOSH MORRISSEY',
    (np.where(espn_events.event_player_1=='P K SUBBAN', 'P.K. SUBBAN',
    (np.where(espn_events.event_player_1=='EGOR SHARANGOVICH', 'YEGOR SHARANGOVICH',
    (np.where(espn_events.event_player_1=='MAXIME COMTOIS', 'MAX COMTOIS',
    (np.where(espn_events.event_player_1=='NICHOLAS CAAMANO', 'NICK CAAMANO',
    (np.where(espn_events.event_player_1=='DANIEL CARCILLO', 'DAN CARCILLO',
    (np.where(espn_events.event_player_1=='ALEXANDER OVECHKIN', 'ALEX OVECHKIN',
    (np.where(espn_events.event_player_1=='MICHAEL CAMMALLERI', 'MIKE CAMMALLERI',
    (np.where(espn_events.event_player_1=='DAVE STECKEL', 'DAVID STECKEL',
    (np.where(espn_events.event_player_1=='JIM DOWD', 'JAMES DOWD', 
    (np.where(espn_events.event_player_1=='MAXIME TALBOT', 'MAX TALBOT',
    (np.where(espn_events.event_player_1=='MIKE ZIGOMANIS', 'MICHAEL ZIGOMANIS',
    (np.where(espn_events.event_player_1=='VINNY PROSPAL', 'VACLAV PROSPAL',
    (np.where(espn_events.event_player_1=='MIKE YORK', 'MICHAEL YORK',
    (np.where(espn_events.event_player_1=='JACOB DOWELL', 'JAKE DOWELL',
    (np.where(espn_events.event_player_1=='MICHAEL RUPP', 'MIKE RUPP',
    (np.where(espn_events.event_player_1=='ALEXEI KOVALEV', 'ALEX KOVALEV',
    (np.where(espn_events.event_player_1=='SLAVA KOZLOV', 'VYACHESLAV KOZLOV',
    (np.where(espn_events.event_player_1=='JEFF HAMILTON', 'JEFFREY HAMILTON',
    (np.where(espn_events.event_player_1=='JOHNNY POHL', 'JOHN POHL',
    (np.where(espn_events.event_player_1=='DANIEL GIRARDI', 'DAN GIRARDI',
    (np.where(espn_events.event_player_1=='NIKOLAI ZHERDEV', 'NIKOLAY ZHERDEV',
    (np.where(espn_events.event_player_1=='J.P. DUMONT', 'J-P DUMONT',
    (np.where(espn_events.event_player_1=='DWAYNE KING', 'DJ KING',
    (np.where(espn_events.event_player_1=='JOHN ODUYA', 'JOHNNY ODUYA',
    (np.where(espn_events.event_player_1=='ROBERT SCUDERI', 'ROB SCUDERI',
    (np.where(espn_events.event_player_1=='DOUG MURRAY', 'DOUGLAS MURRAY',
    (np.where(espn_events.event_player_1=='VACLAV PROSPAL', 'VINNY PROSPAL',
    (np.where(espn_events.event_player_1=='RICH PEVERLY', 'RICH PEVERLEY',
    espn_events.event_player_1.str.strip()
             ))))))))))))))))))))))))))))))))))))))))))))
             ))))))))))))))))))))))))))))))))))))))))))

    espn_events['event_player_1'] = (np.where(espn_events['event_player_1']== "JANIS MOSER" , "J.J. MOSER",
    (np.where(espn_events['event_player_1']== "NICHOLAS PAUL" , "NICK PAUL",
    (np.where(espn_events['event_player_1']== "JACOB MIDDLETON" , "JAKE MIDDLETON",
    (np.where(espn_events['event_player_1']== "TOMMY NOVAK" , "THOMAS NOVAK",
    espn_events['event_player_1']))))))))

    espn_events['event_player_1'] = (np.where(espn_events['event_player_1']== "PAT MAROON" , "PATRICK MAROON",
    (np.where(espn_events['event_player_1']== "JOHHNY BEECHER" , "JOHN BEECHER",
    (np.where(espn_events['event_player_1']== "ALEXANDER BARKOV" , "ALEKSANDER BARKOV",
    (np.where(espn_events['event_player_1']== "TOMMY NOVAK" , "THOMAS NOVAK",
    espn_events['event_player_1']))))))))
    
    espn_events = espn_events.assign(version = 
                       (np.where(
                       (espn_events.event==espn_events.event.shift()) & 
                       (espn_events.event_player_1==espn_events.event_player_1.shift()) &
                       (espn_events.event_player_1!='') &
                       (espn_events.game_seconds==espn_events.game_seconds.shift()),
                        1, 0)))
    
    espn_events = espn_events.assign(version = 
                           (np.where(
                           (espn_events.event==espn_events.event.shift(2)) & 
                           (espn_events.event_player_1==espn_events.event_player_1.shift(2)) &
                           (espn_events.game_seconds==espn_events.game_seconds.shift(2)) & 
                           (espn_events.event_player_1!='') &
                           (~espn_events.description.str.contains('Penalty Shot')),
                            2, espn_events.version)))
    
    espn_events = espn_events.assign(version = 
                           (np.where(
                           (espn_events.event==espn_events.event.shift(3)) & 
                           (espn_events.event_player_1==espn_events.event_player_1.shift(3)) &
                           (espn_events.game_seconds==espn_events.game_seconds.shift(3)) & 
                           (espn_events.event_player_1!=''),
                            3, espn_events.version)))
    
    espn_events['espn_id'] = int(espn_game_id)
    
    espn_events['event_player_1'] = espn_events['event_player_1'].str.strip()
    
    espn_events['event_player_1'] = espn_events['event_player_1'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8').str.upper()
    
    #espn_events = espn_events.assign(event_player_1 = np.where(
    #espn_events.event_player_1=='ALEX BURROWS', 'ALEXANDRE BURROWS', espn_events.event_player_1))
    
    global look
    look = espn_events
    
    espn_events['coords_x'] = np.where(espn_events['coords_x']>99, 99, espn_events['coords_x'])
    espn_events['coords_y'] = np.where(espn_events['coords_y']<(-42), (-42), espn_events['coords_y'])

    if drop_description == True:
        return espn_events.drop(columns = 'description')
    else:
        return espn_events

def scrape_espn_ids_single_game(game_date, home_team, away_team):
    
    gamedays = pd.DataFrame()
    
    if home_team == 'ATLANTA THRASHERS':
        home_team = 'WINNIPEG JETS'
    if away_team == 'ATLANTA THRASHERS':
        away_team = 'WINNIPEG JETS'
        
    if home_team == 'PHOENIX COYOTES':
        home_team = 'ARIZONA COYOTES'
    if away_team == 'PHOENIX COYOTES':
        away_team = 'ARIZONA COYOTES'
    
    this_date = (game_date)
    url = 'http://www.espn.com/nhl/scoreboard?date=' + this_date.replace("-", "")
    page = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout = 500)
    soup = BeautifulSoup(page.content, parser = 'lxml')
    soup_found = soup.find_all('a', {'class':['AnchorLink truncate', 
                             'AnchorLink Button Button--sm Button--anchorLink Button--alt mb4 w-100',
                            'AnchorLink Button Button--sm Button--anchorLink Button--alt mb4 w-100 mr2'], 'href':[re.compile("/nhl/team/_/name/"), re.compile("game/_")]})
    at = []
    ht = []
    gids = []
    fax = pd.DataFrame()
    #print(str(i))
    for i in range (0, ((len(soup_found)))):
        away = soup_found[i]['href'].rsplit('/')[-1].split('-')[0].upper()
        home = soup_found[i]['href'].rsplit('/')[-1].split('-')[-1].upper()
        espnid = soup_found[i]['href'].rsplit('/')[-2]
        at.append(away)
        ht.append(home)
        gids.append(espnid)
    
    fax = fax.assign(
    away_team = at,
    home_team = ht,
    espn_id = gids,
    game_date = pd.to_datetime(this_date))
    
    gamedays = gamedays._append(fax)

    gamedays = gamedays[gamedays.espn_id!='gameId']
    
    gamedays = gamedays.assign(
        home_team = np.where(gamedays.home_team=='ST LOUIS BLUES', 'ST. LOUIS BLUES', gamedays.home_team),
        away_team = np.where(gamedays.away_team=='ST LOUIS BLUES', 'ST. LOUIS BLUES', gamedays.away_team),
        espn_id = gamedays.espn_id.str.split('/').str[0].astype(int)
    
    )
    
    gamedays = gamedays.assign(
        home_team = np.where(gamedays.home_team=='TB', 'TBL',
                    np.where(gamedays.home_team=='T.B', 'TBL',
                    np.where(gamedays.home_team=='L.A', 'LAK',
                    np.where(gamedays.home_team=='LA', 'LAK',
                    np.where(gamedays.home_team=='S.J', 'SJS',
                    np.where(gamedays.home_team=='SJ', 'SJS',
                    np.where(gamedays.home_team=='N.J', 'NJD',
                    np.where(gamedays.home_team=='NJ', 'NJD',
                    gamedays.home_team)))))))),
        away_team = np.where(gamedays.away_team=='TB', 'TBL',
                    np.where(gamedays.away_team=='T.B', 'TBL',
                    np.where(gamedays.away_team=='L.A', 'LAK',
                    np.where(gamedays.away_team=='LA', 'LAK',
                    np.where(gamedays.away_team=='S.J', 'SJS',
                    np.where(gamedays.away_team=='SJ', 'SJS',
                    np.where(gamedays.away_team=='N.J', 'NJD',
                    np.where(gamedays.away_team=='NJ', 'NJD',
                    gamedays.away_team)))))))),
        espn_id = gamedays.espn_id.astype(int))
    
    gamedays = gamedays.assign(
        away_team = np.where(gamedays.away_team=='DUCKS', 'ANA',
                    np.where(gamedays.away_team=='COYOTES', 'ARI',
                    np.where(gamedays.away_team=='BRUINS', 'BOS',
                    np.where(gamedays.away_team=='SABRES', 'BUF',
                    np.where(gamedays.away_team=='FLAMES', 'CGY',
                    np.where(gamedays.away_team=='HURRICANES', 'CAR',
                    np.where(gamedays.away_team=='BLACKHAWKS', 'CHI',
                    np.where(gamedays.away_team=='AVALANCHE', 'COL',
                    np.where(gamedays.away_team=='BLUE', 'CBJ',
                    np.where(gamedays.away_team=='JACKETS', 'CBJ',
                    np.where(gamedays.away_team=='STARS', 'DAL',
                    np.where(gamedays.away_team=='RED', 'DET',
                    np.where(gamedays.away_team=='WINGS', 'DET',
                    np.where(gamedays.away_team=='OILERS', 'EDM',
                    np.where(gamedays.away_team=='PANTHERS', 'FLA',
                    np.where(gamedays.away_team=='KINGS', 'LAK',
                    np.where(gamedays.away_team=='WILD', 'MIN',
                    np.where(gamedays.away_team=='CANADIENS', 'MTL',
                    np.where(gamedays.away_team=='PREDATORS', 'NSH',
                    np.where(gamedays.away_team=='DEVILS', 'NJD',
                    np.where(gamedays.away_team=='ISLANDERS', 'NYI',
                    np.where(gamedays.away_team=='RANGERS', 'NYR',
                    np.where(gamedays.away_team=='SENATORS', 'OTT',
                    np.where(gamedays.away_team=='FLYERS', 'PHI',
                    np.where(gamedays.away_team=='PENGUINS', 'PIT',
                    np.where(gamedays.away_team=='SHARKS', 'SJS',
                    np.where(gamedays.away_team=='KRAKEN', 'SEA',
                    np.where(gamedays.away_team=='BLUES', 'STL',
                    np.where(gamedays.away_team=='LIGHTNING', 'TBL',
                    np.where(gamedays.away_team=='LEAFS', 'TOR',
                    np.where(gamedays.away_team=='MAPLE', 'TOR',
                    np.where(gamedays.away_team=='CANUCKS', 'VAN',
                    np.where(gamedays.away_team=='GOLDEN', 'VGK',
                    np.where(gamedays.away_team=='KNIGHTS', 'VGK',
                    np.where(gamedays.away_team=='CAPITALS', 'WSH',
                    np.where(gamedays.away_team=='JETS', 'WPG',
                    np.where(gamedays.away_team=='CLUB', 'UTA',
                    np.where(gamedays.away_team=='HOCKEY', 'UTA', 'mistake'
                            ))))))))))))))))))))))))))))))))))))))
    )

    gamedays = gamedays.assign(
        home_team = np.where(gamedays.home_team=='DUCKS', 'ANA',
                    np.where(gamedays.home_team=='COYOTES', 'ARI',
                    np.where(gamedays.home_team=='BRUINS', 'BOS',
                    np.where(gamedays.home_team=='SABRES', 'BUF',
                    np.where(gamedays.home_team=='FLAMES', 'CGY',
                    np.where(gamedays.home_team=='HURRICANES', 'CAR',
                    np.where(gamedays.home_team=='BLACKHAWKS', 'CHI',
                    np.where(gamedays.home_team=='AVALANCHE', 'COL',
                    np.where(gamedays.home_team=='BLUE', 'CBJ',
                    np.where(gamedays.home_team=='JACKETS', 'CBJ',
                    np.where(gamedays.home_team=='STARS', 'DAL',
                    np.where(gamedays.home_team=='RED', 'DET',
                    np.where(gamedays.home_team=='WINGS', 'DET',
                    np.where(gamedays.home_team=='OILERS', 'EDM',
                    np.where(gamedays.home_team=='PANTHERS', 'FLA',
                    np.where(gamedays.home_team=='KINGS', 'LAK',
                    np.where(gamedays.home_team=='WILD', 'MIN',
                    np.where(gamedays.home_team=='CANADIENS', 'MTL',
                    np.where(gamedays.home_team=='PREDATORS', 'NSH',
                    np.where(gamedays.home_team=='DEVILS', 'NJD',
                    np.where(gamedays.home_team=='ISLANDERS', 'NYI',
                    np.where(gamedays.home_team=='RANGERS', 'NYR',
                    np.where(gamedays.home_team=='SENATORS', 'OTT',
                    np.where(gamedays.home_team=='FLYERS', 'PHI',
                    np.where(gamedays.home_team=='PENGUINS', 'PIT',
                    np.where(gamedays.home_team=='SHARKS', 'SJS',
                    np.where(gamedays.home_team=='KRAKEN', 'SEA',
                    np.where(gamedays.home_team=='BLUES', 'STL',
                    np.where(gamedays.home_team=='LIGHTNING', 'TBL',
                    np.where(gamedays.home_team=='MAPLE', 'TOR',
                    np.where(gamedays.home_team=='LEAFS', 'TOR',
                    np.where(gamedays.home_team=='CANUCKS', 'VAN',
                    np.where(gamedays.home_team=='GOLDEN', 'VGK',
                    np.where(gamedays.home_team=='KNIGHTS', 'VGK',
                    np.where(gamedays.home_team=='CAPITALS', 'WSH',
                    np.where(gamedays.home_team=='JETS', 'WPG', 
                    np.where(gamedays.home_team=='CLUB', 'UTA', 
                    np.where(gamedays.home_team=='HOCKEY', 'UTA', 'mistake'
                            ))))))))))))))))))))))))))))))))))))))
    )
    
    gamedays = gamedays[(gamedays.game_date==this_date) & (gamedays.home_team==home_team) & (gamedays.away_team==away_team)] 
        
    return(gamedays)

def merge_and_prepare(events, shifts):
    
    season = str(int(str(events.game_id.iloc[0])[:4])) + str(int(str(events.game_id.iloc[0])[:4]) + 1)
    small_id = str(events.game_id.iloc[0])[5:]
    game_id = int(events.game_id.iloc[0])
    
    merged = pd.concat([events, shifts])
    
    merged = merged.assign(home_team = merged[~(pd.isna(merged.home_team))].home_team.iloc[0],
                          away_team = merged[~(pd.isna(merged.away_team))].away_team.iloc[0],
                          home_team_abbreviated = merged[~(pd.isna(merged.home_team_abbreviated))].home_team_abbreviated.iloc[0],
                          away_team_abbreviated = merged[~(pd.isna(merged.away_team_abbreviated))].away_team_abbreviated.iloc[0])

    merged = merged.assign(event_team = np.where(merged.team==merged.home_team, merged.home_team_abbreviated, 
                                        np.where(merged.team==merged.away_team, merged.away_team_abbreviated, 
                                                 merged.event_team)))

    merged = merged.assign(event = np.where((pd.isna(merged.event)) & 
                                     ((~pd.isna(merged.number_off)) | (~pd.isna(merged.number_on))), "CHANGE", merged.event))

    home_space = ' ' + merged['home_team_abbreviated'].iloc[0]
    away_space = ' ' + merged['away_team_abbreviated'].iloc[0]

    merged['away_skaters'] = np.where(pd.isna(merged.away_skaters), '\xa0', merged.away_skaters)

    merged['tmp'] = merged.away_skaters.str.replace("[^0-9]", " ")

    merged['tmp2'] = (merged.tmp.str.strip().str.split("  ")).apply(lambda x: natsorted(x)).apply(lambda x: ' '.join(x))

    merged['tmp2'] = (merged.away_team_abbreviated.iloc[0] + merged.tmp2).str.replace(" ", away_space).str.replace(" ", ", ")

    merged['tmp2'] = np.where(merged.tmp2.str.strip()==merged.away_team_abbreviated.iloc[0], '\xa0', merged.tmp2)

    merged['away_on_ice'] = merged['tmp2']

    merged['home_skaters'] = np.where(pd.isna(merged.home_skaters), '\xa0', merged.home_skaters)

    merged['tmp'] = merged.home_skaters.str.replace("[^0-9]", " ")

    merged['tmp2'] = (merged.tmp.str.strip().str.split("  ")).apply(lambda x: natsorted(x)).apply(lambda x: ' '.join(x))

    merged['tmp2'] = (merged.home_team_abbreviated.iloc[0] + merged.tmp2).str.replace(" ", home_space).str.replace(" ", ", ")

    merged['tmp2'] = np.where(merged.tmp2.str.strip()==merged.home_team_abbreviated.iloc[0], '\xa0', merged.tmp2)

    merged['home_on_ice'] = merged['tmp2']

    merged = merged.sort_values(by = ['game_seconds', 'period'])

    merged = merged.assign(jumping_on = (np.where(merged.home_team == merged.team, (merged.home_team_abbreviated.iloc[0] + merged.on_numbers).str.replace(", ", home_space).str.replace(" ", ", "), 
                                   np.where(merged.away_team == merged.team, (merged.away_team_abbreviated.iloc[0] + merged.on_numbers).str.replace(", ", away_space).str.replace(" ", ", "),
                                            '\xa0'))),
                          jumping_off = (np.where(merged.home_team == merged.team, (merged.home_team_abbreviated.iloc[0] + merged.off_numbers).str.replace(", ", home_space).str.replace(" ", ", "), 
                                   np.where(merged.away_team == merged.team, (merged.away_team_abbreviated.iloc[0] + merged.off_numbers).str.replace(", ", away_space).str.replace(" ", ", "),
                                            '\xa0'))),
                          prio = np.where(merged.event=="CHANGE", 0,
                                          np.where(merged.event.isin(['PGSTR', 'PGEND', 'PSTR', 'PEND', 'ANTHEM']), -1, 1))).sort_values(
        by = ['game_seconds', 'period', 'event_index'])

    merged = merged.assign(change_before_event = np.where(
        (
            (merged.away_on_ice!='') & (merged.event.shift()=='CHANGE') & (merged.away_on_ice!=merged.away_on_ice.shift()) | 
            (merged.home_on_ice!='') & (merged.event.shift()=='CHANGE') & (merged.home_on_ice!=merged.home_on_ice.shift())
        ), 1, 0
    ))

    merged = merged.assign(change_prio = 
                          np.where((merged.team==merged.home_team) & (merged.event=='CHANGE') , 1,
                                  np.where((merged.team==merged.away_team) & (merged.event=='CHANGE'), -1, 0)))

    merged = merged.assign(priority = np.where(merged.event.isin(['TAKE', 'GIVE', 'MISS', 'HIT', 'SHOT', 'BLOCK']), 1, 
                                                np.where(merged.event=="GOAL", 2,
                                                    np.where(merged.event=="STOP", 3,
                                                        np.where(merged.event=="DELPEN", 4,
                                                            np.where(merged.event=="PENL", 5,
                                                                np.where(merged.event=="CHANGE", 6,
                                                                    np.where(merged.event=="PEND", 7,
                                                                        np.where(merged.event=="GEND", 8,
                                                                            np.where(merged.event=="FAC", 9, 0)))))))))).sort_values(by = ['game_seconds', 'period', 'priority', 'event_index', 'change_prio'])

    merged = merged.reset_index(drop = True).reset_index().rename(columns = {'index':'event_index', 'event_index':'original_index'})

    global roster

    roster = scrape_html_roster(season, small_id).rename(columns = {'Nom/Name':'Name'})

    roster = roster.assign(team_abbreviated = np.where(roster.team=='home', 
                                                       merged.home_team_abbreviated.iloc[0],
                                                      merged.away_team_abbreviated.iloc[0]))

    roster = roster.assign(teamnum = roster.team_abbreviated + roster['#'],
                          Name = roster.Name.str.split('(').str[0].str.strip())

    roster = roster.assign(Name = np.where((roster.Name=='SEBASTIAN AHO') &( roster.team_name == 'NEW YORK ISLANDERS'), 'SEBASTIAN AHO (SWE)', roster.Name))

    goalies = roster[(roster.Pos=='G') & (roster.status!='scratch')]

    away_roster = roster[(roster.team=='away') & (roster.status!='scratch')]
    home_roster = roster[(roster.team=='home') & (roster.status!='scratch')]

    merged.jumping_on = np.where(pd.isna(merged.jumping_on), '\xa0', merged.jumping_on)
    merged.jumping_off = np.where(pd.isna(merged.jumping_off), '\xa0', merged.jumping_off)

    awaydf = pd.DataFrame()

    for i in range(0, len(away_roster)):
        vec = pd.DataFrame(
                np.cumsum(
                    (np.where(merged.jumping_on.str.split(', ').apply(lambda x: away_roster.teamnum.iloc[i] in x)==True, 1, 0)) - (
                    np.where((merged.jumping_off.str.split(', ').apply(lambda x: away_roster.teamnum.iloc[i] in x)==True) & (merged.event=='CHANGE'), 1, 0))
                                     ))
        awaydf = pd.concat([awaydf, vec], axis = 1)

    awaydf.columns = away_roster.Name

    global homedf

    homedf = pd.DataFrame()

    for i in range(0, len(home_roster)):
        vec = pd.DataFrame(
                np.cumsum(
                    (np.where(merged.jumping_on.str.split(', ').apply(lambda x: home_roster.teamnum.iloc[i] in x)==True, 1, 0)) - (
                    np.where((merged.jumping_off.str.split(', ').apply(lambda x: home_roster.teamnum.iloc[i] in x)==True) & (merged.event=='CHANGE'), 1, 0))
                                     ))
        homedf = pd.concat([homedf, vec], axis = 1)

    homedf.columns = home_roster.Name

    global home_on
    global away_on

    home_on = pd.DataFrame((homedf==1).apply(lambda y: homedf.columns[y.tolist()].tolist(), axis=1))
    home_on[0] = (home_on[0].apply(','.join)).apply(lambda x: ','.join(natsorted(x.split(','))))

    away_on = pd.DataFrame((awaydf==1).apply(lambda y: awaydf.columns[y.tolist()].tolist(), axis=1))
    away_on[0] = (away_on[0].apply(','.join)).apply(lambda x: ','.join(natsorted(x.split(','))))

    away_on = away_on[0].str.split(',', expand=True).rename(columns = {0:'away_on_1', 1:'away_on_2', 2:'away_on_3', 3:'away_on_4', 4:'away_on_5', 5:'away_on_6', 6:'away_on_7', 7:'away_on_8', 8:'away_on_9'})
    home_on = home_on[0].str.split(',', expand=True).rename(columns = {0:'home_on_1', 1:'home_on_2', 2:'home_on_3', 3:'home_on_4', 4:'home_on_5', 5:'home_on_6', 6:'home_on_7', 7:'home_on_8', 8:'home_on_9'})

    if 'away_on_1' not in away_on:
        away_on['away_on_1'] = '\xa0'
    if 'away_on_2' not in away_on:
        away_on['away_on_2'] = '\xa0'
    if 'away_on_3' not in away_on:
        away_on['away_on_3'] = '\xa0'
    if 'away_on_4' not in away_on:
        away_on['away_on_4'] = '\xa0'
    if 'away_on_5' not in away_on:
        away_on['away_on_5'] = '\xa0'
    if 'away_on_6' not in away_on:
        away_on['away_on_6'] = '\xa0'
    if 'away_on_7' not in away_on:
        away_on['away_on_7'] = '\xa0'
    if 'away_on_8' not in away_on:
        away_on['away_on_8'] = '\xa0'
    if 'away_on_9' not in away_on:
        away_on['away_on_9'] = '\xa0'
    if 'home_on_1' not in home_on:
        home_on['home_on_1'] = '\xa0'
    if 'home_on_2' not in home_on:
        home_on['home_on_2'] = '\xa0'
    if 'home_on_3' not in home_on:
        home_on['home_on_3'] = '\xa0'
    if 'home_on_4' not in home_on:
        home_on['home_on_4'] = '\xa0'
    if 'home_on_5' not in home_on:
        home_on['home_on_5'] = '\xa0'
    if 'home_on_6' not in home_on:
        home_on['home_on_6'] = '\xa0'
    if 'home_on_7' not in home_on:
        home_on['home_on_7'] = '\xa0'
    if 'home_on_8' not in home_on:
        home_on['home_on_8'] = '\xa0'
    if 'home_on_9' not in home_on:
        home_on['home_on_9'] = '\xa0'

    game = pd.concat([merged, home_on, away_on], axis = 1)

    game = game.assign(
    event_team = np.where(game.event_team==game.home_team, game.home_team_abbreviated,
                         np.where(game.event_team==game.away_team, game.away_team_abbreviated,
                                 game.event_team)),
    description = game.description.astype(str))

    game['description'] = np.where(game.description=='nan', '\xa0', game.description)

    game = game.drop(columns = ['original_index', 'strength', 'original_time', 'home_team', 'away_team', 'other_team', 'event_player_str',
                                'version', 'team', 'change_before_event', 'prio', 'change_prio', 'priority', 'tmp', 'tmp2']).rename(
        columns = {'away_team_abbreviated':'away_team', 'home_team_abbreviated':'home_team', 'coordsx':'coords_x', 'coordsy':'coords_y',
                  'ep1_name':'event_player_1', 'ep2_name':'event_player_2', 'ep3_name':'event_player_3'}).assign(
    game_id = int(game_id),
    season = int(season),
    event_zone = game.description.apply(lambda x: re.search('(\S+?) Zone', x)).apply(lambda x: group_if_not_none(x)),
    event_detail = 
           np.where(game.event.isin(['SHOT', 'BLOCK', 'MISS', 'GOAL']), 
                    game.description.str.split(', ').str[1].str.strip(),
                        np.where(game.event.isin(["PSTR", "PEND", "SOC", "GEND"]),
                        game.description.str.split(': ').str[1].str.strip(),
                                np.where(game.event=='PENL', 
                                game.description.str.split('(').str[1].str.split(')').str[0].str.strip(),
                                        np.where(game.event=='CHANGE',
                                        game.description.str.split(' - ').str[0].str.strip(),
                                            np.where(pd.isna(game.description), '\xa0',
                                                    '\xa0'))))))

    game = game.assign(home_goalie = np.where(
    game.home_on_1.isin(goalies.Name), game.home_on_1,
    np.where(
    game.home_on_2.isin(goalies.Name), game.home_on_2,
    np.where(
    game.home_on_3.isin(goalies.Name), game.home_on_3,
    np.where(
    game.home_on_4.isin(goalies.Name), game.home_on_4,
    np.where(
    game.home_on_5.isin(goalies.Name), game.home_on_5,
    np.where(
    game.home_on_6.isin(goalies.Name), game.home_on_6,
    np.where(
    game.home_on_7.isin(goalies.Name), game.home_on_7,
    np.where(
    game.home_on_8.isin(goalies.Name), game.home_on_8,
    np.where(
    game.home_on_9.isin(goalies.Name), game.home_on_9,
    '\xa0'))))))))),
    away_goalie = np.where(
    game.away_on_1.isin(goalies.Name), game.away_on_1,
    np.where(
    game.away_on_2.isin(goalies.Name), game.away_on_2,
    np.where(
    game.away_on_3.isin(goalies.Name), game.away_on_3,
    np.where(
    game.away_on_4.isin(goalies.Name), game.away_on_4,
    np.where(
    game.away_on_5.isin(goalies.Name), game.away_on_5,
    np.where(
    game.away_on_6.isin(goalies.Name), game.away_on_6,
    np.where(
    game.away_on_7.isin(goalies.Name), game.away_on_7,
    np.where(
    game.away_on_8.isin(goalies.Name), game.away_on_8,
    np.where(
    game.away_on_9.isin(goalies.Name), game.away_on_9,
    '\xa0'))))))))))

    game = game.assign(
    away_on_1 = np.where((pd.isna(game.away_on_1)) | (game.away_on_1 is None) | (game.away_on_1=='') | (game.away_on_1=='\xa0'), '\xa0', game.away_on_1),
    away_on_2 = np.where((pd.isna(game.away_on_2)) | (game.away_on_2 is None) | (game.away_on_2=='') | (game.away_on_2=='\xa0'), '\xa0', game.away_on_2),
    away_on_3 = np.where((pd.isna(game.away_on_3)) | (game.away_on_3 is None) | (game.away_on_3=='') | (game.away_on_3=='\xa0'), '\xa0', game.away_on_3),
    away_on_4 = np.where((pd.isna(game.away_on_4)) | (game.away_on_4 is None) | (game.away_on_4=='') | (game.away_on_4=='\xa0'), '\xa0', game.away_on_4),
    away_on_5 = np.where((pd.isna(game.away_on_5)) | (game.away_on_5 is None) | (game.away_on_5=='') | (game.away_on_5=='\xa0'), '\xa0', game.away_on_5),
    away_on_6 = np.where((pd.isna(game.away_on_6)) | (game.away_on_6 is None) | (game.away_on_6=='') | (game.away_on_6=='\xa0'), '\xa0', game.away_on_6),
    away_on_7 = np.where((pd.isna(game.away_on_7)) | (game.away_on_7 is None) | (game.away_on_7=='') | (game.away_on_7=='\xa0'), '\xa0', game.away_on_7),
    away_on_8 = np.where((pd.isna(game.away_on_8)) | (game.away_on_8 is None) | (game.away_on_8=='') | (game.away_on_8=='\xa0'), '\xa0', game.away_on_8),
    away_on_9 = np.where((pd.isna(game.away_on_9)) | (game.away_on_9 is None) | (game.away_on_9=='') | (game.away_on_9=='\xa0'), '\xa0', game.away_on_9),
    home_on_1 = np.where((pd.isna(game.home_on_1)) | (game.home_on_1 is None) | (game.home_on_1=='') | (game.home_on_1=='\xa0'), '\xa0', game.home_on_1),
    home_on_2 = np.where((pd.isna(game.home_on_2)) | (game.home_on_2 is None) | (game.home_on_2=='') | (game.home_on_2=='\xa0'), '\xa0', game.home_on_2),
    home_on_3 = np.where((pd.isna(game.home_on_3)) | (game.home_on_3 is None) | (game.home_on_3=='') | (game.home_on_3=='\xa0'), '\xa0', game.home_on_3),
    home_on_4 = np.where((pd.isna(game.home_on_4)) | (game.home_on_4 is None) | (game.home_on_4=='') | (game.home_on_4=='\xa0'), '\xa0', game.home_on_4),
    home_on_5 = np.where((pd.isna(game.home_on_5)) | (game.home_on_5 is None) | (game.home_on_5=='') | (game.home_on_5=='\xa0'), '\xa0', game.home_on_5),
    home_on_6 = np.where((pd.isna(game.home_on_6)) | (game.home_on_6 is None) | (game.home_on_6=='') | (game.home_on_6=='\xa0'), '\xa0', game.home_on_6),
    home_on_7 = np.where((pd.isna(game.home_on_7)) | (game.home_on_7 is None) | (game.home_on_7=='') | (game.home_on_7=='\xa0'), '\xa0', game.home_on_7),
    home_on_8 = np.where((pd.isna(game.home_on_8)) | (game.home_on_8 is None) | (game.home_on_8=='') | (game.home_on_8=='\xa0'), '\xa0', game.home_on_8),
    home_on_9 = np.where((pd.isna(game.home_on_9)) | (game.home_on_9 is None) | (game.home_on_9=='') | (game.home_on_9=='\xa0'), '\xa0', game.home_on_9),
    home_goalie = np.where((pd.isna(game.home_goalie)) | (game.home_goalie is None) | (game.home_goalie=='') | (game.home_goalie=='\xa0'), '\xa0', game.home_goalie),
    away_goalie = np.where((pd.isna(game.away_goalie)) | (game.away_goalie is None) | (game.away_goalie=='') | (game.away_goalie=='\xa0'), '\xa0', game.away_goalie)
    )

    game = game.assign(home_skaters = 
                       np.where(game.home_on_1!='\xa0', 1, 0) + np.where(game.home_on_2!='\xa0', 1, 0) + np.where(game.home_on_3!='\xa0', 1, 0) + np.where(game.home_on_4!='\xa0', 1, 0) + 
                       np.where(game.home_on_5!='\xa0', 1, 0) + np.where(game.home_on_6!='\xa0', 1, 0) + np.where(game.home_on_7!='\xa0', 1, 0) + np.where(game.home_on_8!='\xa0', 1, 0) +
                       np.where(game.home_on_9!='\xa0', 1, 0) - np.where((game.home_goalie!='\xa0') & ((game.period<5) | (game.game_id.astype(str).str[5].astype(int)==3)), 1, 0),
                       away_skaters = 
                       np.where(game.away_on_1!='\xa0', 1, 0) + np.where(game.away_on_2!='\xa0', 1, 0) + np.where(game.away_on_3!='\xa0', 1, 0) + np.where(game.away_on_4!='\xa0', 1, 0) + 
                       np.where(game.away_on_5!='\xa0', 1, 0) + np.where(game.away_on_6!='\xa0', 1, 0) + np.where(game.away_on_7!='\xa0', 1, 0) + np.where(game.away_on_8!='\xa0', 1, 0) +
                       np.where(game.away_on_9!='\xa0', 1, 0) - np.where((game.away_goalie!='\xa0') & ((game.period<5) | (game.game_id.astype(str).str[5].astype(int)==3)), 1, 0))

    game = game.assign(home_skater_temp = 
                np.where((game.home_goalie=='\xa0') , 'E', game.home_skaters),
           away_skater_temp = 
                np.where((game.away_goalie=='\xa0') , 'E', game.away_skaters))

    game = game.assign(game_strength_state = (game.home_skater_temp.astype(str)) + 'v' + (game.away_skater_temp.astype(str)),
                      event_zone = np.where(game.event_zone is not None, game.event_zone.str.replace(". Zone", ""), ''),
                      home_score = np.cumsum(np.where((game.event.shift()=='GOAL') & (((game.period<5) | (game.game_id.astype(str).str[5].astype(int)==3))) & (game.event_team.shift()==game.home_team), 1, 0)),
                      away_score = np.cumsum(np.where((game.event.shift()=='GOAL') & (((game.period<5) | (game.game_id.astype(str).str[5].astype(int)==3))) & (game.event_team.shift()==game.away_team), 1, 0))).drop(
        columns = ['home_skater_temp', 'away_skater_temp'])

    game = game.assign(game_score_state = (game.home_score.astype(str)) + 'v' + (game.away_score.astype(str)),
                      game_date = pd.to_datetime(game.game_date[~pd.isna(game.game_date)].iloc[0])
                      )

    game.number_off = np.where((game.jumping_on!='\xa0') & (game.jumping_off=='\xa0'), 0, game.number_off)
    game.number_on = np.where((game.jumping_off!='\xa0') & (game.jumping_on=='\xa0'), 0, game.number_on)

    so = game[game.period==5]

    if len(so)>0 and int(game.game_id.astype(str).str[5].iloc[0]) != 3:
        game = game[game.period<5]
        home = roster[roster.team=='home'].rename(columns = {'teamnum':'home_on_ice', 'Name':'home_goalie_name'}).loc[:, ['home_goalie_name', 'home_on_ice']]
        away = roster[roster.team=='away'].rename(columns = {'teamnum':'away_on_ice', 'Name':'away_goalie_name'}).loc[:, ['away_goalie_name', 'away_on_ice']]
        so = so.merge(away, how = 'left', indicator = True).drop(columns = ['_merge']).merge(home, how = 'left')
        so = so.assign(
        home_goalie = so.home_goalie_name,
        away_goalie = so.away_goalie_name).drop(columns = ['away_goalie_name', 'home_goalie_name'])
        so_winner = so[so.event=='GOAL'].groupby('event_team')['event', 'home_team'].count().reset_index().sort_values(by = ['event', 'event_team'],ascending = False).event_team.iloc[0]
        so = so.assign(
            home_on_1 = so.home_goalie,
            away_on_1 = so.away_goalie,
            home_on_2 = np.where(so.event_team==so.home_team, so.event_player_1, '\xa0'),
            away_on_2 = np.where(so.event_team==so.away_team, so.event_player_1, '\xa0'))
        if len(so[so.event=='PEND'])>0:
            end_event = so[so.event=='PEND'].index.astype(int)[0]
            so = so.assign(
            home_score = np.where((so.index>=end_event) & (so_winner == so.home_team), 1+so.home_score, so.home_score),
            away_score = np.where((so.index>=end_event) & (so_winner == so.away_team), 1+so.away_score, so.away_score))
        game = pd.concat([game, so])

    game['event_length'] = game.game_seconds.shift(-1) - game.game_seconds
    game['event_length'] = (np.where((pd.isna(game.event_length)) | (game.event_length<0), 0, game.event_length)).astype(int)
    game['event_index'] = game.event_index + 1
    
    if 'coords_x' and 'coords_y' in game.columns:
    
        columns = ['season', 'game_id', 'game_date', 'event_index',
        'period', 'game_seconds', 'event', 'description',
        'event_detail', 'event_zone', 'event_team', 'event_player_1',
        'event_player_2', 'event_player_3', 'event_length', 'coords_x',
        'coords_y', 'number_on', 'number_off', 'jumping_on', 'jumping_off',
        'home_on_1', 'home_on_2', 'home_on_3', 'home_on_4', 'home_on_5',
        'home_on_6', 'home_on_7', 'home_on_8', 'home_on_9', 'away_on_1', 'away_on_2', 'away_on_3',
        'away_on_4', 'away_on_5', 'away_on_6', 'away_on_7', 'away_on_8', 'away_on_9', 'home_goalie',
        'away_goalie', 'home_team', 'away_team', 'home_skaters', 'away_skaters',
        'home_score', 'away_score', 'game_score_state', 'game_strength_state', 'coordinate_source']
        
    else:
        
        columns = ['season', 'game_id', 'game_date', 'event_index',
        'period', 'game_seconds', 'event', 'description',
        'event_detail', 'event_zone', 'event_team', 'event_player_1',
        'event_player_2', 'event_player_3', 'event_length', 
        'number_on', 'number_off', 'jumping_on', 'jumping_off',
        'home_on_1', 'home_on_2', 'home_on_3', 'home_on_4', 'home_on_5',
        'home_on_6', 'home_on_7', 'home_on_8', 'home_on_9', 'away_on_1', 'away_on_2', 'away_on_3',
        'away_on_4', 'away_on_5', 'away_on_6', 'away_on_7', 'away_on_8', 'away_on_9', 'home_goalie',
        'away_goalie', 'home_team', 'away_team', 'home_skaters', 'away_skaters',
        'home_score', 'away_score', 'game_score_state', 'game_strength_state']

    game = game.loc[:, columns].rename(
    columns = {'period':'game_period', 'event':'event_type', 'description':'event_description', 'number_on':'num_on', 'number_off':'num_off',
              'jumping_on':'players_on', 'jumping_off':'players_off'}
    )

    return(game)

def fix_missing(single, event_coords, events):
    
    # FIRST FIX: EVENTS THAT HAVE MATCHING PERIOD, SECONDS, AND EVENT TYPE, AND ONLY OCCURRED ONCE, BUT NO EVENT PLAYER. #
    global event_coords_temp
    global single_problems
    global merged_problems
    problems = events[(events.event.isin(ewc)) & (pd.isna(events.coords_x))]
    single_problems = problems.groupby(['event', 'period', 'game_seconds'])[
        'event_index'].count().reset_index().rename(
        columns = {'event_index':'problematic_events'})
    # Keep events where only one event of that class happened at that moment.
    single_problems = single_problems[single_problems.problematic_events==1]
    single_problems = problems.merge(single_problems).drop(
        columns = ['problematic_events', 'coords_x', 'coords_y', 'coordinate_source']) # x/y come back later!
    event_coords_temp = event_coords.loc[:, ['period', 'game_seconds', 'event', 'version', 'coords_x', 'coordinate_source']].groupby(
    ['game_seconds', 'period', 'event', 'version'])['coords_x'].count().reset_index().rename(
        columns = {'coords_x':'problematic_events'})
    event_coords_temp = event_coords_temp[event_coords_temp.problematic_events==1].drop(columns = 'problematic_events')
    event_coords_temp = event_coords_temp.merge(event_coords.loc[:, ['game_seconds', 'period', 'event', 'version', 'coords_x', 'coords_y', 'coordinate_source']])
    if 'espn_id' in event_coords_temp.columns:
        event_coords_temp = event_coords_temp.drop(columns = 'espn_id')
    merged_problems = single_problems.merge(event_coords_temp)
    #print("You fixed: " + str(len(merged_problems)) + " events!")
    events = events[~(events.event_index.isin(list(merged_problems.event_index)))]
    events = pd.concat([events, merged_problems.loc[:, list(events.columns)]]).sort_values(by = ['event_index', 'period', 'game_seconds'])
    #if len(merged_problems)>0:
        #events = events[~events.event_index.isin(merged_problems.event_index)]
        #events = pd.concat([events, merged_problems.loc[:, list(events.columns)]]).sort_values(by = ['event_index', 'period', 'game_seconds'])
    look = events
    
    # SECOND FIX: EVENTS THAT HAVE MATCHING PERIOD, EVENT TYPE, AND PLAYER ONE, AND ONLY OCCURRED ONCE, BUT NO GAME SECONDS.
    
    problems = events[(events.event.isin(ewc)) & (pd.isna(events.coords_x))]
    single_problems = problems.groupby(['event', 'period', 'event_player_1'])[
        'event_index'].count().reset_index().rename(
        columns = {'event_index':'problematic_events'})
    # Keep events where only one event of that class happened at that moment.
    single_problems = single_problems[single_problems.problematic_events==1]
    single_problems = problems.merge(single_problems).drop(
        columns = ['problematic_events', 'coords_x', 'coords_y', 'coordinate_source']) # x/y come back later!
    event_coords_temp = event_coords.loc[:, ['period', 'event_player_1', 'event', 
                                        'version', 'coords_x', 'coordinate_source']].groupby(
    ['event_player_1', 'period', 'event', 'version'])['coords_x'].count().reset_index().rename(
        columns = {'coords_x':'problematic_events'})
    event_coords_temp = event_coords_temp[event_coords_temp.problematic_events==1].drop(columns = 'problematic_events')
    event_coords_temp = event_coords_temp.merge(event_coords.loc[:, ['event_player_1', 'period', 'event', 'version', 'coords_x', 'coords_y', 'coordinate_source']])
    merged_problems = single_problems.merge(event_coords_temp)
    #print("You fixed: " + str(len(merged_problems)) + " events!")
    events = events[~events.event_index.isin(merged_problems.event_index)]
    events = pd.concat([events, merged_problems]).sort_values(by = ['event_index', 'period', 'game_seconds'])
    
    return(events)

def full_scrape_1by1(game_id_list, shift_to_espn = True):
    
    global single
    global event_coords
    global full
    global fixed_events
    global events
    
    full = pd.DataFrame()
    
    i = 0
    
    while i in range(0, len(game_id_list)) and len(game_id_list)>0:
       
        # First thing to try: Scraping HTML events
        
        try:
            first_time = time.time()
            print(game_id_list[i]) 
            game_id = game_id_list[i]
            print('Attempting scrape for: ' + str(game_id))
            season = str(int(str(game_id)[:4])) + str(int(str(game_id)[:4]) + 1)
            small_id = str(game_id)[5:]
            single = scrape_html_events(season, small_id)
            single['game_id'] = int(game_id)
            
            # If all goes well with the HTML scrape:
            
            try:
                event_coords = scrape_api_events(game_id, shift_to_espn = shift_to_espn)
                api_coords = event_coords
                api_coords['coordinate_source'] = 'api'
                if len(event_coords[(event_coords.event.isin(ewc)) & (pd.isna(event_coords.coords_x))]) > 0:
                    raise ExpatError('Bad takes, dude!')
                event_coords['game_id'] = int(game_id)
                events = single.merge(event_coords, on = ['event_player_1', 'game_seconds', 'version', 'period', 'game_id', 'event'], how = 'left')
                try:
                    events = fix_missing(single, event_coords, events)
                except IndexError as e:
                    print('Issue when fixing problematic events. Here it is: ' + str(e))
                    continue
                try:
                    shifts = scrape_html_shifts(season, small_id)
                    finalized = merge_and_prepare(events, shifts)
                    full = full._append(finalized)
                    second_time = time.time()
                except IndexError as e:
                    print('There was no shift data for this game. Error: ' + str(e))
                    fixed_events = events
                    fixed_events = fixed_events.rename(
                    columns = {'period':'game_period', 'event':'event_type', 'away_team_abbreviated':'away_team', 
                              'home_team_abbreviated':'home_team', 'description':'event_description', 'home_team':'hometeamfull',
                              'away_team':'awayteamfull'}
                    ).drop(
                    columns = ['original_time', 'other_team', 'strength', 'event_player_str', 'version', 'hometeamfull', 'awayteamfull']
                    ).assign(game_warning = 'NO SHIFT DATA.')
                    full = full._append(fixed_events)
                print('Successfully scraped ' + str(game_id) + '. Coordinates sourced from the API.')
                print("This game took " + str(round(second_time - first_time, 2)) + " seconds.")
                i = i + 1
                
                # If there is an issue with the API:
                
            except KeyError: 
                print('The API gave us trouble with: ' + str(game_id) + '. Let us try ESPN.')
                
                try:
                    home_team = single['home_team_abbreviated'].iloc[0]
                    away_team = single['away_team_abbreviated'].iloc[0]
                    game_date = single['game_date'].iloc[0]
                    try:
                        espn_id = scrape_espn_ids_single_game(str(game_date.date()), home_team, away_team).espn_id.iloc[0]
                        event_coords = scrape_espn_events(int(espn_id))
                        event_coords['coordinate_source'] = 'espn'
                        events = single.merge(event_coords, on = ['event_player_1', 'game_seconds', 'period', 'version', 'event'], how = 'left').drop(columns = ['espn_id'])
                        try:
                            events = fix_missing(single, event_coords, events)
                        except IndexError as e:
                            print('Issue when fixing problematic events. Here it is: ' + str(e))
                            continue
                    except IndexError:
                        print('This game does not have ESPN or API coordinates. You will get it anyway, though.')
                        events = single
                    try:
                        shifts = scrape_html_shifts(season, small_id)
                        finalized = merge_and_prepare(events, shifts)
                        full = full._append(finalized)
                        second_time = time.time()
                    except IndexError as e:
                        print('There was no shift data for this game. Error: ' + str(e))
                        fixed_events = events
                        fixed_events = fixed_events.rename(
                        columns = {'period':'game_period', 'event':'event_type', 'away_team_abbreviated':'away_team', 
                                  'home_team_abbreviated':'home_team', 'description':'event_description', 'home_team':'hometeamfull',
                                  'away_team':'awayteamfull'}
                        ).drop(
                        columns = ['original_time', 'other_team', 'strength', 'event_player_str', 'version', 'hometeamfull', 'awayteamfull']
                        ).assign(game_warning = 'NO SHIFT DATA', season = season)
                        fixed_events['coordinate_source'] = 'espn'
                        full = full._append(fixed_events)
                    second_time = time.time()
                    # Fix this so it doesn't say sourced from ESPN if no coords.
                    if single.equals(events):
                        print("This game took " + str(round(second_time - first_time, 2)) + " seconds.")
                        i = i + 1
                    else:
                        print('Successfully scraped ' + str(game_id) + '. Coordinates sourced from ESPN.')
                        print("This game took " + str(round(second_time - first_time, 2)) + " seconds.")
                        i = i + 1
                    
                    # If there are issues with ESPN
                    
                except KeyError as e:
                    print('ESPN also had trouble scraping coordinates for: ' + str(game_id) + '. Looks like we will need to punt this one, unfortunately.')
                    print('KeyError: ' + str(e))
                    i = i + 1
                    continue
                except IndexError as e:
                    print('ESPN also had trouble scraping coordinates for: ' + str(game_id) + '. Looks like we will need to punt this one, unfortunately.')
                    print('IndexError: ' + str(e))
                    i = i + 1
                    continue
                except TypeError as e:
                    print('ESPN also had trouble scraping coordinates for: ' + str(game_id) + '. Looks like we will need to punt this one, unfortunately.')
                    print('TypeError: ' + str(e))
                    i = i + 1
                    continue
                except ExpatError as e:
                    print('ESPN also had trouble scraping coordinates for: ' + str(game_id) + '. Looks like we will need to punt this one, unfortunately.')
                    print('ExpatError: ' + str(e))
                    i = i + 1
                    continue
                
            except ExpatError:
                print('There was a rare error with the API; numerous takeaways did not have location coordinates for: ' + str(game_id) + '. Let us try ESPN.')
                
                try:
                    home_team = single['home_team'].iloc[0]
                    away_team = single['away_team'].iloc[0]
                    game_date = single['game_date'].iloc[0]
                    try:
                        espn_id = scrape_espn_ids_single_game(str(game_date.date()), home_team, away_team).espn_id.iloc[0]
                        event_coords = scrape_espn_events(int(espn_id))
                        duped_coords = api_coords.assign(source = 'api').merge(event_coords.drop(columns = 'espn_id'), on = ['game_seconds', 'event', 'period', 'version', 'event_player_1'], how = 'outer', indicator = True)
                        # Coordinates are flipped in some games.
                        if len(duped_coords[duped_coords.coords_x_x * -1 == duped_coords.coords_x_y])/len(duped_coords):
                            duped_coords['coords_x_y'] = duped_coords['coords_x_y'] * (-1)
                        if len(duped_coords[duped_coords.coords_y_x * -1 == duped_coords.coords_y_y])/len(duped_coords):
                            duped_coords['coords_y_y'] = duped_coords['coords_y_y'] * (-1)
                        duped_coords['source'] = np.where((pd.isna(duped_coords.source)) | ((pd.isna(duped_coords.coords_x_x)) & ~pd.isna(duped_coords.coords_x_y)), 'espn', duped_coords.source)
                        duped_coords = duped_coords.assign(coords_x = np.where(pd.isna(duped_coords.coords_x_x), duped_coords.coords_x_y, duped_coords.coords_x_x),
                                          coords_y = np.where(pd.isna(duped_coords.coords_y_x), duped_coords.coords_y_y, duped_coords.coords_y_x))
                        col_list = list(api_coords.columns)
                        col_list._append('source')
                        duped_coords = duped_coords.loc[:, col_list]
                        duped_coords = duped_coords[duped_coords.event.isin(['SHOT', 'HIT', 'BLOCK', 'MISS', 'GIVE', 'TAKE', 'GOAL', 'PENL', 'FAC'])]
                        duped_coords = duped_coords[~duped_coords.duplicated()]
                        event_coords = duped_coords
                        events = single.merge(event_coords, on = ['event_player_1', 'game_seconds', 'period', 'version', 'event'], how = 'left')#.drop(columns = ['espn_id'])
                        try:
                            events = fix_missing(single, event_coords, events)
                            events['coordinate_source'] = events['source']
                        except IndexError as e:
                            print('Issue when fixing problematic events. Here it is: ' + str(e))
                    except IndexError as e:
                        if event_coords is not None:
                            print('Okay, ESPN had issues. We will go back to the API for this one. Issue: ' + str(e))
                            events = single.merge(event_coords, on = ['event_player_1', 'game_seconds', 'version', 'period', 'event'], how = 'left')
                            try:
                                events = fix_missing(single, event_coords, events)
                            except IndexError as e:
                                print('Issue when fixing problematic events. Here it is: ' + str(e))
                        else:
                            print('This game does not have ESPN or API coordinates. You will get it anyway, though. Issue: ' + str(e))
                            events = single
                            events['coordinate_source'] = 'none'
                    try:
                        shifts = scrape_html_shifts(season, small_id)
                        finalized = merge_and_prepare(events, shifts)
                        full = full._append(finalized)
                        second_time = time.time()
                    except IndexError as e:
                        print('There was no shift data for this game. Error: ' + str(e))
                        fixed_events = events
                        fixed_events = fixed_events.rename(
                        columns = {'period':'game_period', 'event':'event_type', 'away_team_abbreviated':'away_team', 
                                  'home_team_abbreviated':'home_team', 'description':'event_description', 'home_team':'hometeamfull',
                                  'away_team':'awayteamfull'}
                        ).drop(
                        columns = ['original_time', 'other_team', 'strength', 'event_player_str', 'version', 'hometeamfull', 'awayteamfull']
                        ).assign(game_warning = 'NO SHIFT DATA', season = season)
                        full = full._append(fixed_events)
                    second_time = time.time()
                    # Fix this so it doesn't say sourced from ESPN if no coords.
                    print('Successfully scraped ' + str(game_id) + '. Coordinates sourced from ESPN.')
                    print("This game took " + str(round(second_time - first_time, 2)) + " seconds.")
                    i = i + 1
                    
                    # If there are issues with ESPN
                    
                except KeyError as e:
                    print('ESPN also had trouble scraping coordinates for: ' + str(game_id) + '. Looks like we will need to punt this one, unfortunately.')
                    print('KeyError: ' + str(e))
                    i = i + 1
                    continue
                except IndexError as e:
                    print('ESPN also had trouble scraping coordinates for: ' + str(game_id) + '. Looks like we will need to punt this one, unfortunately.')
                    print('IndexError: ' + str(e))
                    i = i + 1
                    continue
                except TypeError as e:
                    print('ESPN also had trouble scraping coordinates for: ' + str(game_id) + '. Looks like we will need to punt this one, unfortunately.')
                    print('TypeError: ' + str(e))
                    i = i + 1
                    continue
                except ExpatError as e:
                    print('ESPN also had trouble scraping coordinates for: ' + str(game_id) + '. Looks like we will need to punt this one, unfortunately.')
                    print('ExpatError: ' + str(e))
                    i = i + 1
                    continue
            
        except ConnectionError:
            print('Got a Connection Error, time to sleep.')
            time.sleep(10)
            continue
            
        except ChunkedEncodingError:
            print('Got a Connection Error, time to sleep.')
            time.sleep(10)
            continue
            
        except AttributeError as e:
            print(str(game_id) + ' does not have an HTML report. Here is the error: ' + str(e))
            i = i + 1
            continue
            
        except IndexError as e:
            print(str(game_id) + ' has an issue with the HTML Report. Here is the error: ' + str(e))
            i = i + 1
            continue
            
        except ValueError as e:
            print(str(game_id) + ' has an issue with the HTML Report. Here is the error: ' + str(e))
            i = i + 1
            continue

        except KeyError as k:
            print(str(game_id) + 'gave some kind of Key Error. Here is the error: ' + str(e))
            i = i + 1
            continue
            
        except KeyboardInterrupt:
            print('You manually interrupted the scrape. You will get to keep every game you have already completed scraping after just a bit of post-processing. Good bye.')
            global hidden_patrick
            hidden_patrick = 1
            if len(full) > 0:
                
                full = full.assign(home_skaters = np.where(~full.home_skaters.isin([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                                             (full.home_skaters.apply(lambda x: len(re.findall('[A-Z]', str(x)))) - 
                                                             full.home_skaters.apply(lambda x: len(re.findall('[G]', str(x))))),
                                                             full.home_skaters))

                full = full.assign(away_skaters = np.where(~full.away_skaters.isin([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                                             (full.away_skaters.apply(lambda x: len(re.findall('[A-Z]', str(x)))) - 
                                                             full.away_skaters.apply(lambda x: len(re.findall('[G]', str(x))))),
                                                             full.away_skaters))
                
                if 'away_on_1' in full.columns:
                
                    full = full.assign(
                    away_on_1 = np.where((pd.isna(full.away_on_1)) | (full.away_on_1 is None) | (full.away_on_1=='') | (full.away_on_1=='\xa0'), '\xa0', full.away_on_1),
                    away_on_2 = np.where((pd.isna(full.away_on_2)) | (full.away_on_2 is None) | (full.away_on_2=='') | (full.away_on_2=='\xa0'), '\xa0', full.away_on_2),
                    away_on_3 = np.where((pd.isna(full.away_on_3)) | (full.away_on_3 is None) | (full.away_on_3=='') | (full.away_on_3=='\xa0'), '\xa0', full.away_on_3),
                    away_on_4 = np.where((pd.isna(full.away_on_4)) | (full.away_on_4 is None) | (full.away_on_4=='') | (full.away_on_4=='\xa0'), '\xa0', full.away_on_4),
                    away_on_5 = np.where((pd.isna(full.away_on_5)) | (full.away_on_5 is None) | (full.away_on_5=='') | (full.away_on_5=='\xa0'), '\xa0', full.away_on_5),
                    away_on_6 = np.where((pd.isna(full.away_on_6)) | (full.away_on_6 is None) | (full.away_on_6=='') | (full.away_on_6=='\xa0'), '\xa0', full.away_on_6),
                    away_on_7 = np.where((pd.isna(full.away_on_7)) | (full.away_on_7 is None) | (full.away_on_7=='') | (full.away_on_7=='\xa0'), '\xa0', full.away_on_7),
                    away_on_8 = np.where((pd.isna(full.away_on_8)) | (full.away_on_8 is None) | (full.away_on_8=='') | (full.away_on_8=='\xa0'), '\xa0', full.away_on_8),
                    away_on_9 = np.where((pd.isna(full.away_on_9)) | (full.away_on_9 is None) | (full.away_on_9=='') | (full.away_on_9=='\xa0'), '\xa0', full.away_on_9),
                    home_on_1 = np.where((pd.isna(full.home_on_1)) | (full.home_on_1 is None) | (full.home_on_1=='') | (full.home_on_1=='\xa0'), '\xa0', full.home_on_1),
                    home_on_2 = np.where((pd.isna(full.home_on_2)) | (full.home_on_2 is None) | (full.home_on_2=='') | (full.home_on_2=='\xa0'), '\xa0', full.home_on_2),
                    home_on_3 = np.where((pd.isna(full.home_on_3)) | (full.home_on_3 is None) | (full.home_on_3=='') | (full.home_on_3=='\xa0'), '\xa0', full.home_on_3),
                    home_on_4 = np.where((pd.isna(full.home_on_4)) | (full.home_on_4 is None) | (full.home_on_4=='') | (full.home_on_4=='\xa0'), '\xa0', full.home_on_4),
                    home_on_5 = np.where((pd.isna(full.home_on_5)) | (full.home_on_5 is None) | (full.home_on_5=='') | (full.home_on_5=='\xa0'), '\xa0', full.home_on_5),
                    home_on_6 = np.where((pd.isna(full.home_on_6)) | (full.home_on_6 is None) | (full.home_on_6=='') | (full.home_on_6=='\xa0'), '\xa0', full.home_on_6),
                    home_on_7 = np.where((pd.isna(full.home_on_7)) | (full.home_on_7 is None) | (full.home_on_7=='') | (full.home_on_7=='\xa0'), '\xa0', full.home_on_7),
                    home_on_8 = np.where((pd.isna(full.home_on_8)) | (full.home_on_8 is None) | (full.home_on_8=='') | (full.home_on_8=='\xa0'), '\xa0', full.home_on_8),
                    home_on_9 = np.where((pd.isna(full.home_on_9)) | (full.home_on_9 is None) | (full.home_on_9=='') | (full.home_on_9=='\xa0'), '\xa0', full.home_on_9),
                    home_goalie = np.where((pd.isna(full.home_goalie)) | (full.home_goalie is None) | (full.home_goalie=='') | (full.home_goalie=='\xa0'), '\xa0', full.home_goalie),
                    away_goalie = np.where((pd.isna(full.away_goalie)) | (full.away_goalie is None) | (full.away_goalie=='') | (full.away_goalie=='\xa0'), '\xa0', full.away_goalie)
                    )
                
            return full
    
    if len(full) > 0:
                
        full = full.assign(home_skaters = np.where(~full.home_skaters.isin([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                                             (full.home_skaters.apply(lambda x: len(re.findall('[A-Z]', str(x)))) - 
                                                             full.home_skaters.apply(lambda x: len(re.findall('[G]', str(x))))),
                                                             full.home_skaters))

        full = full.assign(away_skaters = np.where(~full.away_skaters.isin([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
                                                     (full.away_skaters.apply(lambda x: len(re.findall('[A-Z]', str(x)))) - 
                                                     full.away_skaters.apply(lambda x: len(re.findall('[G]', str(x))))),
                                                     full.away_skaters))

        if 'away_on_1' in full.columns:

            full = full.assign(
            away_on_1 = np.where((pd.isna(full.away_on_1)) | (full.away_on_1 is None) | (full.away_on_1=='') | (full.away_on_1=='\xa0'), '\xa0', full.away_on_1),
            away_on_2 = np.where((pd.isna(full.away_on_2)) | (full.away_on_2 is None) | (full.away_on_2=='') | (full.away_on_2=='\xa0'), '\xa0', full.away_on_2),
            away_on_3 = np.where((pd.isna(full.away_on_3)) | (full.away_on_3 is None) | (full.away_on_3=='') | (full.away_on_3=='\xa0'), '\xa0', full.away_on_3),
            away_on_4 = np.where((pd.isna(full.away_on_4)) | (full.away_on_4 is None) | (full.away_on_4=='') | (full.away_on_4=='\xa0'), '\xa0', full.away_on_4),
            away_on_5 = np.where((pd.isna(full.away_on_5)) | (full.away_on_5 is None) | (full.away_on_5=='') | (full.away_on_5=='\xa0'), '\xa0', full.away_on_5),
            away_on_6 = np.where((pd.isna(full.away_on_6)) | (full.away_on_6 is None) | (full.away_on_6=='') | (full.away_on_6=='\xa0'), '\xa0', full.away_on_6),
            away_on_7 = np.where((pd.isna(full.away_on_7)) | (full.away_on_7 is None) | (full.away_on_7=='') | (full.away_on_7=='\xa0'), '\xa0', full.away_on_7),
            away_on_8 = np.where((pd.isna(full.away_on_8)) | (full.away_on_8 is None) | (full.away_on_8=='') | (full.away_on_8=='\xa0'), '\xa0', full.away_on_8),
            away_on_9 = np.where((pd.isna(full.away_on_9)) | (full.away_on_9 is None) | (full.away_on_9=='') | (full.away_on_9=='\xa0'), '\xa0', full.away_on_9),
            home_on_1 = np.where((pd.isna(full.home_on_1)) | (full.home_on_1 is None) | (full.home_on_1=='') | (full.home_on_1=='\xa0'), '\xa0', full.home_on_1),
            home_on_2 = np.where((pd.isna(full.home_on_2)) | (full.home_on_2 is None) | (full.home_on_2=='') | (full.home_on_2=='\xa0'), '\xa0', full.home_on_2),
            home_on_3 = np.where((pd.isna(full.home_on_3)) | (full.home_on_3 is None) | (full.home_on_3=='') | (full.home_on_3=='\xa0'), '\xa0', full.home_on_3),
            home_on_4 = np.where((pd.isna(full.home_on_4)) | (full.home_on_4 is None) | (full.home_on_4=='') | (full.home_on_4=='\xa0'), '\xa0', full.home_on_4),
            home_on_5 = np.where((pd.isna(full.home_on_5)) | (full.home_on_5 is None) | (full.home_on_5=='') | (full.home_on_5=='\xa0'), '\xa0', full.home_on_5),
            home_on_6 = np.where((pd.isna(full.home_on_6)) | (full.home_on_6 is None) | (full.home_on_6=='') | (full.home_on_6=='\xa0'), '\xa0', full.home_on_6),
            home_on_7 = np.where((pd.isna(full.home_on_7)) | (full.home_on_7 is None) | (full.home_on_7=='') | (full.home_on_7=='\xa0'), '\xa0', full.home_on_7),
            home_on_8 = np.where((pd.isna(full.home_on_8)) | (full.home_on_8 is None) | (full.home_on_8=='') | (full.home_on_8=='\xa0'), '\xa0', full.home_on_8),
            home_on_9 = np.where((pd.isna(full.home_on_9)) | (full.home_on_9 is None) | (full.home_on_9=='') | (full.home_on_9=='\xa0'), '\xa0', full.home_on_9),
            home_goalie = np.where((pd.isna(full.home_goalie)) | (full.home_goalie is None) | (full.home_goalie=='') | (full.home_goalie=='\xa0'), '\xa0', full.home_goalie),
            away_goalie = np.where((pd.isna(full.away_goalie)) | (full.away_goalie is None) | (full.away_goalie=='') | (full.away_goalie=='\xa0'), '\xa0', full.away_goalie)
            )

    return full

def full_scrape(game_id_list, shift = False):
    
    global hidden_patrick
    hidden_patrick = 0
    
    df = full_scrape_1by1(game_id_list, shift_to_espn = shift)
    
    if (hidden_patrick==0) and (len(df)>0):
        
        gids = list(set(df.game_id))
        missing = [x for x in game_id_list if x not in gids]
        if len(missing)>0:
            print('You missed the following games: ' + str(missing))
            print('Let us try scraping each of them one more time.')
            retry = full_scrape_1by1(missing)
            df = df._append(retry)
            return df
        else:
            return df
    
    else:
        return df

print("Welcome to the TopDownHockey NHL Scraper, built by Patrick Bacon.")
print("If you enjoy the scraper and would like to support my work, or you have any comments, questions, or concerns, feel free to follow me on Twitter @TopDownHockey or reach out to me via email at patrick.s.bacon@gmail.com. Have fun!")
