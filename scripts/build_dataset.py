#!/usr/bin/env python3
"""Build verified 53-episode dataset for Leonard Bernstein's Young People's Concerts."""

import json
import os
import re
import time
import urllib.parse
import urllib.request

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.environ.get(
    "YPC_SOURCE_DIR",
    os.path.expanduser("~/.gemini/antigravity/brain/03b05728-4e0e-4307-a772-15b66dbdb9a8"),
)
MD_PATH = os.environ.get("YPC_MD_PATH", os.path.join(SOURCE_DIR, "young_peoples_concerts_53_episodes.md"))
BILI_P1 = os.path.join(SOURCE_DIR, "scratch", "bili_p1.json")
BILI_P2 = os.path.join(SOURCE_DIR, "scratch", "bili_p2.json")
LB_INDEX = os.path.join(SOURCE_DIR, "scratch", "lb_ypc_index.html")
CACHE_PATH = os.path.join(ROOT_DIR, "scripts", "itunes_cache.json")
OUT_JSON = os.path.join(ROOT_DIR, "src", "data", "episodes.json")

# Exact mapping of the 48 Bilibili videos in 掘火中译 season 966776 to Episode 1..53
# Missing from season 966776 (confirmed absent from 掘火中译): Ep 11, 14, 19, 30, 42
MISSING_BILI_EPS = {11, 14, 19, 30, 42}

# Exact mapping from Ep No. to leonardbernstein.com script URL slug (44 scripts; 9 Young Performers 2-9 & Alumni Reunion have no online script)
NO_SCRIPT_EPS = {14, 19, 22, 25, 30, 35, 37, 39, 42}

# Verified repertoire per episode (cross-checked against official transcripts & Wikipedia)
REPERTOIRE = {
    1: [
        ("Rossini", "William Tell Overture", "威廉·退尔序曲"),
        ("Richard Strauss", "Don Quixote", "堂吉诃德"),
        ("Beethoven", "Symphony No. 6 in F Major, Op. 68 (Pastoral)", "第六交响曲“田园”"),
        ("Mussorgsky", "Pictures at an Exhibition", "图画展览会"),
        ("Tchaikovsky", "Symphony No. 4 in F Minor, Op. 36", "第四交响曲"),
        ("Tchaikovsky", "Symphony No. 5 in E Minor, Op. 64", "第五交响曲"),
        ("Webern", "Six Pieces for Orchestra, Op. 6", "管弦乐曲六首"),
        ("Ravel", "La Valse", "圆舞曲"),
    ],
    2: [
        ("Gershwin", "An American in Paris", "一个美国人在巴黎"),
        ("George W. Chadwick", "Melpomene Overture", "墨尔波墨涅序曲"),
        ("Dvořák", "Symphony No. 9 in E Minor (From the New World)", "第九交响曲“自新大陆”"),
        ("Edward MacDowell", "Indian Suite, Op. 48", "印第安组曲"),
        ("Henry F. Gilbert", "The Dance in Place Congo", "刚果广场舞曲"),
        ("Copland", "Music for the Theatre", "剧院音乐"),
        ("Gershwin", "Rhapsody in Blue", "蓝色狂想曲"),
        ("William Schuman", "American Festival Overture", "美国节日序曲"),
        ("Roy Harris", "Symphony No. 3", "第三交响曲"),
        ("Copland", "Billy the Kid", "比利小子"),
        ("Virgil Thomson", "The Mother of Us All", "我们大家的母亲"),
        ("Randall Thompson", "Symphony No. 2", "第二交响曲"),
        ("Copland", "Symphony No. 3 (Finale)", "第三交响曲终曲（科普兰亲执棒）"),
    ],
    3: [
        ("Rimsky-Korsakov", "Capriccio Espagnol, Op. 34", "西班牙随想曲"),
        ("Debussy", "Prélude à l'après-midi d'un faune", "牧神午后前奏曲"),
        ("Gershwin", "Rhapsody in Blue", "蓝色狂想曲"),
        ("J. S. Bach", "Brandenburg Concerto No. 3 in G Major", "第三勃兰登堡协奏曲"),
        ("Prokofiev", "Peter and the Wolf", "彼得与狼"),
        ("Hindemith", "Kleine Kammermusik, Op. 24, No. 2", "小室内乐五重奏"),
        ("Mozart", "Serenade No. 10 in B-flat Major (Gran Partita)", "十三管乐小夜曲"),
        ("Stravinsky", "Symphonies of Wind Instruments", "管乐交响曲"),
        ("Beethoven", "String Quartet No. 14 in C-sharp Minor, Op. 131", "升 c 小调弦乐四重奏"),
        ("Schubert", "String Quintet in C Major, D. 956", "C 大调弦乐五重奏"),
        ("Vaughan Williams", "Fantasia on a Theme by Thomas Tallis", "塔利斯主题幻想曲"),
        ("William Schuman", "Symphony for Strings (Symphony No. 5)", "弦乐交响曲"),
        ("Gabrieli", "Sonata pian' e forte (octi toni)", "八声部奏鸣曲"),
        ("Saul Goodman", "Canon for Percussion", "打击乐卡农"),
        ("Stravinsky", "L'Histoire du soldat (March)", "士兵的故事进行曲"),
        ("Ravel", "Boléro", "波莱罗"),
    ],
    4: [
        ("Mozart", "Symphony No. 41 in C Major, K. 551 (Jupiter)", "第 41 交响曲“朱庇特”终曲"),
        ("Beethoven", "Symphony No. 5 in C Minor, Op. 67", "第五交响曲"),
        ("Sibelius", "Symphony No. 5 in E-flat Major, Op. 82", "第五交响曲"),
        ("Tchaikovsky", "Symphony No. 4 in F Minor, Op. 36", "第四交响曲终曲"),
        ("Kenneth Alford", "Colonel Bogey March", "波基上校进行曲"),
        ("Beethoven", "Symphony No. 3 in E-flat Major (Eroica)", "第三交响曲“英雄”终曲"),
        ("Elvis Presley", "All Shook Up", "心神摇荡"),
        ("Tchaikovsky", "Romeo and Juliet Fantasy Overture", "罗密欧与朱丽叶幻想序曲"),
        ("Gershwin", "Rhapsody in Blue", "蓝色狂想曲"),
        ("Brahms", "Symphony No. 2 in D Major, Op. 73 (Finale)", "第二交响曲末乐章"),
    ],
    5: [
        ("Handel", "Water Music", "水上音乐"),
        ("Beethoven", "Symphony No. 5 in C Minor, Op. 67", "第五交响曲"),
        ("Rimsky-Korsakov", "Scheherazade, Op. 35", "天方夜谭"),
        ("Mozart", "Piano Concerto No. 21 in C Major, K. 467", "第 21 钢琴协奏曲"),
        ("J. S. Bach", "Brandenburg Concerto No. 4 in G Major", "第四勃兰登堡协奏曲"),
        ("Mozart", "Overture to The Marriage of Figaro", "费加罗的婚礼序曲"),
        ("Haydn", "Symphony No. 102 in B-flat Major (Finale)", "第 102 交响曲末乐章"),
        ("Chopin", "Fantaisie in F Minor, Op. 49", "f 小调幻想曲"),
        ("Schumann", "Symphony No. 2 in C Major, Op. 61", "第二交响曲"),
        ("Beethoven", "Egmont Overture, Op. 84", "艾格蒙特序曲"),
    ],
    6: [
        ("Walter Piston", "The Incredible Flutist (Ballet Suite)", "神奇的长笛手组曲"),
        ("Paul White", "Mosquito Dance", "蚊子舞"),
        ("Gershwin", "An American in Paris", "一个美国人在巴黎"),
        ("Kodály", "Háry János Suite", "哈里·亚诺什组曲"),
        ("Rameau", "La Poule", "母鸡"),
        ("Haydn", "Symphony No. 88 in G Major (Finale)", "第 88 交响曲末乐章"),
        ("Prokofiev", "Symphony No. 1 in D Major (Classical)", "第一交响曲“古典”"),
        ("Mahler", "Symphony No. 1 in D Major (3rd Movement)", "第一交响曲第三乐章"),
        ("Wagner", "Prelude to Tristan and Isolde", "特里斯坦与伊索尔德前奏曲"),
        ("Richard Strauss", "Der Rosenkavalier (Prelude)", "玫瑰骑士前奏曲"),
        ("Mozart", "A Musical Joke, K. 522", "音乐玩笑"),
        ("Shostakovich", "Polka from The Golden Age, Op. 22", "黄金时代波尔卡"),
        ("Copland", "Burlesque from Music for the Theatre", "剧院音乐：滑稽曲"),
        ("Dukas", "The Sorcerer's Apprentice", "魔法师的弟子"),
        ("Brahms", "Symphony No. 4 in E Minor, Op. 98 (Scherzo)", "第四交响曲第三乐章谐谑曲"),
    ],
    7: [
        ("Vivaldi", "Concerto for Two Mandolins in G Major, RV 532 / C Major Ensemble", "双曼陀林与乐队协奏曲"),
        ("J. S. Bach", "Brandenburg Concerto No. 5 in D Major", "第五勃兰登堡协奏曲"),
        ("Mozart", "Sinfonia Concertante in E-flat Major, K. 364", "交响协奏曲"),
        ("Mendelssohn", "Violin Concerto in E Minor, Op. 64", "e 小调小提琴协奏曲"),
        ("Bartók", "Concerto for Orchestra (4th & 5th Movements)", "乐队协奏曲第四、五乐章"),
    ],
    8: [
        ("Mahler", "Symphony No. 4 in G Major", "第四交响曲"),
        ("Mahler", "Das Lied von der Erde (Youth & The Farewell)", "大地之歌（青春与告别）"),
        ("Mahler", "Symphony No. 2 in C Minor (Resurrection)", "第二交响曲“复活”"),
        ("Mahler", "Des Knaben Wunderhorn (St. Anthony's Sermon to the Fish)", "少年魔号：圣安东尼向鱼群布道"),
    ],
    9: [
        ("Dvořák", "Cello Concerto in B Minor, Op. 104 (1st Movement)", "b 小调大提琴协奏曲第一乐章"),
        ("Wieniawski", "Violin Concerto No. 2 in D Minor, Op. 22 (Finale)", "第二小提琴协奏曲终曲"),
        ("Prokofiev", "Peter and the Wolf, Op. 67", "彼得与狼"),
    ],
    10: [
        ("Villa-Lobos", "Bachianas Brasileiras No. 2 (The Little Train of the Caipira)", "凯皮拉的小火车"),
        ("Francisco de la Torre", "Alta (Danza)", "古西班牙舞曲（肖姆管）"),
        ("Giovanni Gabrieli", "Canzon septimi toni", "八声部坎佐纳"),
        ("J. S. Bach", "Brandenburg Concerto No. 4 in G Major (1st Movement)", "第四勃兰登堡协奏曲（古今乐器对比）"),
        ("Luening & Ussachevsky", "Concerted Piece for Tape Recorder and Orchestra", "磁带录音机与管弦乐队协奏曲"),
        ("Mark Bucci", "Concerto for a Singing Instrument (Kazoo Concerto)", "卡祖笛与管弦乐队协奏曲"),
    ],
    11: [
        ("Copland", "The Second Hurricane (A Play Opera in Two Acts)", "第二次飓风（青年戏剧歌剧）"),
    ],
    12: [
        ("Rossini", "Semiramide Overture", "塞米拉米德序曲"),
        ("Beethoven", "Leonore Overture No. 3, Op. 72b", "莱奥诺拉第三序曲"),
        ("Debussy", "Prélude à l'après-midi d'un faune", "牧神午后前奏曲"),
        ("Bernstein", "Candide Overture", "坎迪德序曲"),
    ],
    13: [
        ("Copland", "An Outdoor Overture", "户外序曲"),
        ("Copland", "Statements for Orchestra (Dogmatic)", "声明：教条"),
        ("Copland", "Dance from Music for the Theatre", "剧院音乐：舞曲"),
        ("Copland", "Grover's Corners from Our Town", "我们的小镇：格罗弗角"),
        ("Copland", "Hoe-Down from Rodeo", "牛仔竞技：锄地舞曲"),
        ("Copland", "The Boatmen's Dance & I Bought Me a Cat (Old American Songs)", "美国老歌两首"),
        ("Copland", "El Salón México", "墨西哥沙龙"),
    ],
    14: [
        ("Dvořák", "Cello Concerto in B Minor, Op. 104 (3rd Movement)", "b 小调大提琴协奏曲第三乐章"),
        ("Chopin", "Piano Concerto No. 1 in E Minor, Op. 11", "第一钢琴协奏曲"),
        ("Puccini", "Addio, senza rancor from La Bohème", "波希米亚人：咪咪的告别"),
        ("Menotti", "Hello, Hello from The Telephone", "电话：喂，喂"),
        ("Britten", "The Young Person's Guide to the Orchestra, Op. 34", "青少年管弦乐队指南"),
    ],
    15: [
        ("Mozart", "Symphony No. 39 in E-flat Major, K. 543 (3rd Movement)", "第 39 交响曲小步舞曲"),
        ("Bartók", "Music for Strings, Percussion and Celesta", "弦乐、打击乐与钢片琴音乐"),
        ("Ravel", "Daphnis et Chloé", "达夫尼斯与克洛埃"),
        ("Carlos Chávez", "Sinfonía India (Symphony No. 2)", "印第安交响曲"),
        ("Canteloube", "Chants d'Auvergne (Songs of the Auvergne)", "奥弗涅牧歌选段"),
        ("Charles Ives", "Symphony No. 2 (Finale)", "第二交响曲终曲"),
    ],
    16: [
        ("Debussy", "La Mer", "大海（三乐章全曲）"),
        ("Debussy", "Voiles from Préludes, Book I", "前奏曲：帆"),
        ("Debussy", "Poissons d'or from Images, Set II", "意象集：金鱼"),
        ("Debussy", "La Puerta del Vino from Préludes, Book II", "前奏曲：维诺之门"),
        ("Debussy", "Golliwog's Cakewalk from Children's Corner", "儿童天地：黑娃娃的步态舞"),
        ("Ravel", "Daphnis et Chloé, Suite No. 2 (Final Dance)", "达夫尼斯与克洛埃第二组曲终舞"),
    ],
    17: [
        ("Gershwin", "An American in Paris", "一个美国人在巴黎"),
        ("Ernest Bloch", "Schelomo (Rhapsodie Hébraïque)", "所罗门（大提琴狂想曲）"),
        ("Manuel de Falla", "Two Dances from The Three-Cornered Hat", "三角帽双舞曲"),
    ],
    18: [
        ("Stravinsky", "Greeting Prelude (Happy Birthday)", "祝贺前奏曲（生日快乐）"),
        ("Stravinsky", "The Rite of Spring", "春之祭"),
        ("Stravinsky", "Concerto in E-flat (Dumbarton Oaks)", "敦巴顿橡树园协奏曲"),
        ("Stravinsky", "Agon", "阿贡"),
        ("Stravinsky", "Petrushka", "彼得鲁什卡（全四幕）"),
    ],
    19: [
        ("Mozart", "Overture to The Marriage of Figaro", "费加罗的婚礼序曲（小泽征尔指挥）"),
        ("Ernest Bloch", "Prayer from Jewish Life", "祈祷（加里·卡尔低音提琴）"),
        ("Paganini / Rossini", "Moses Fantasy (arr. Gary Karr)", "摩西主题幻想曲"),
        ("Saint-Saëns", "The Carnival of the Animals", "动物狂欢节"),
    ],
    20: [
        ("Berlioz", "Roman Carnival Overture, Op. 9", "罗马狂欢节序曲"),
        ("Copland", "The Little Horses (Old American Songs)", "小马驹"),
        ("Vivaldi", "Concerto for Four Violins in B Minor, Op. 3, No. 10", "b 小调四小提琴协奏曲"),
        ("William Walton", "Façade (Tango Pasodoble)", "门面：西班牙斗牛舞探戈"),
        ("Tchaikovsky", "1812 Overture, Op. 49", "1812 序曲"),
    ],
    21: [
        ("Wagner", "Prelude to Tristan and Isolde", "特里斯坦与伊索尔德前奏曲"),
        ("Mozart", "Symphony No. 40 in G Minor, K. 550 (1st Movement)", "第 40 交响曲第一乐章"),
        ("J. S. Bach", "Italian Concerto, BWV 971 (2nd Movement)", "意大利协奏曲第二乐章"),
        ("Hindemith", "Concert Music for Strings and Brass, Op. 50", "弦乐与铜管协奏音乐"),
        ("Brahms", "Symphony No. 4 in E Minor, Op. 98 (Finale)", "第四交响曲末乐章"),
    ],
    22: [
        ("Mozart", "Piano Concerto No. 23 in A Major, K. 488", "第 23 钢琴协奏曲（三少女接力）"),
        ("Liszt", "Piano Concerto No. 1 in E-flat Major", "第一钢琴协奏曲（安德烈·瓦茨首秀）"),
    ],
    23: [
        ("Oscar Lorenzo Fernandez", "Batuque from Reisado do Pastoreio", "巴图克舞曲"),
        ("Villa-Lobos", "Bachianas Brasileiras No. 5", "巴西的巴赫风第 5 号"),
        ("Silvestre Revueltas", "Sensemayá", "森塞玛雅"),
        ("Copland", "Danzón Cubano", "古巴达松舞曲"),
        ("Bernstein", "Symphonic Dances from West Side Story", "西区故事交响舞曲"),
    ],
    24: [
        ("Mussorgsky", "Prelude to Khovanshchina", "霍万兴那前奏曲"),
        ("Randall Thompson", "Symphony No. 2 in E Minor (Scherzo)", "第二交响曲谐谑曲"),
        ("Walter Piston", "Suite from The Incredible Flutist", "神奇的长笛手组曲"),
        ("Brahms", "Academic Festival Overture, Op. 80", "学院节日序曲"),
    ],
    25: [
        ("Handel", "Harp Concerto in B-flat Major, Op. 4, No. 6", "降 B 大调竖琴协奏曲"),
        ("Ravel", "Introduction and Allegro", "引子与快板（阿巴多指挥）"),
        ("Shulamit Ran", "Capriccio for Piano and Orchestra", "钢琴与乐队随想曲"),
        ("Bartók", "Rhapsody No. 1 for Cello and Orchestra", "第一狂想曲"),
        ("Rossini", "William Tell Overture", "威廉·退尔序曲"),
    ],
    26: [
        ("Hindemith", "String Quartet No. 3, Op. 22", "第三弦乐四重奏"),
        ("Hindemith", "Kleine Kammermusik, Op. 24, No. 2 (1st Movement)", "小室内乐第一乐章"),
        ("Hindemith", "Symphony: Mathis der Maler", "画家马蒂斯交响曲"),
    ],
    27: [
        ("Gunther Schuller", "Journey into Jazz (Narr. Nat Hentoff)", "爵士之旅"),
        ("Copland", "Concerto for Piano and Orchestra (1926)", "钢琴协奏曲（科普兰亲奏）"),
        ("Larry Austin", "Improvisations for Orchestra and Jazz Soloists", "管弦乐与爵士独奏家即兴曲"),
    ],
    28: [
        ("Mozart", "Symphony No. 41 in C Major, K. 551 (Jupiter, 1st Movement)", "朱庇特交响曲第一乐章"),
        ("The Beatles", "And I Love Her", "我爱她"),
        ("Bizet", "Je dis que rien ne m'épouvante (Micaëla's Aria) from Carmen", "卡门：米凯拉咏叹调"),
        ("Mozart", "Piano Sonata in C Major, K. 545", "C 大调钢琴奏鸣曲"),
        ("Prokofiev", "Symphony No. 1 (Classical, Finale)", "古典交响曲终曲"),
    ],
    29: [
        ("Reinhold Glière", "Russian Sailors' Dance from The Red Poppy", "俄罗斯水手舞"),
        ("Anton Webern", "Five Pieces for Orchestra, Op. 10, No. 1", "管弦乐五首"),
        ("Toshiro Mayuzumi", "Pieces for Prepared Piano and String Quartet", "预置钢琴与弦乐四重奏"),
        ("Milton Babbitt", "Composition for Twelve Instruments", "十二件乐器作品"),
        ("Luigi Nono", "Incontri for 24 Instruments", "24 件乐器相遇"),
        ("Wagner", "Prelude to Die Meistersinger von Nürnberg", "纽伦堡的名歌手前奏曲"),
        ("Charles Ives", "The Fourth of July", "独立日"),
        ("Manuel de Falla", "The Three-Cornered Hat (Part I Dances)", "三角帽第一部舞曲"),
        ("Smetana", "The Moldau (Vltava)", "沃尔塔瓦河"),
    ],
    30: [
        ("Mozart", "Piano Concerto No. 20 in D Minor, K. 466 (1st Movement)", "第 20 钢琴协奏曲第一乐章"),
        ("Mendelssohn", "Violin Concerto in E Minor, Op. 64", "e 小调小提琴协奏曲"),
        ("Ravel", "Ma mère l'Oye (Mother Goose Suite)", "鹅妈妈组曲"),
    ],
    31: [
        ("Sibelius", "Finlandia, Op. 26", "芬兰颂"),
        ("Sibelius", "Violin Concerto in D Minor, Op. 47 (1st Movement)", "d 小调小提琴协奏曲第一乐章"),
        ("Sibelius", "Symphony No. 2 in D Major, Op. 43 (Finale)", "第二交响曲终曲"),
    ],
    32: [
        ("Wagner", "Prelude to Act III of Lohengrin", "罗恩格林第三幕前奏曲"),
        ("Johann Strauss II", "The Blue Danube Waltz", "蓝色多瑙河"),
        ("The Beatles", "Help!", "救命！"),
        ("Brahms", "Symphony No. 4 in E Minor, Op. 98 (1st Movement)", "第四交响曲第一乐章"),
        ("Vaughan Williams", "Symphony No. 4 in F Minor (Finale)", "第四交响曲末乐章"),
    ],
    33: [
        ("Haydn", "Symphony No. 88 in G Major", "第 88 交响曲"),
        ("Beethoven", "Symphony No. 5 in C Minor, Op. 67", "第五交响曲"),
        ("Brahms", "Symphony No. 1 in C Minor, Op. 68", "第一交响曲"),
        ("Debussy", "Ibéria (Images pour orchestre)", "伊比利亚"),
        ("Stravinsky", "The Royal March from L'Histoire du soldat", "士兵的故事：皇家进行曲"),
        ("Gershwin", "An American in Paris", "一个美国人在巴黎"),
        ("Copland", "Hoe-Down from Rodeo", "牛仔竞技：锄地舞曲"),
    ],
    34: [
        ("Shostakovich", "Symphony No. 7 in C Major, Op. 60 (Leningrad)", "第七交响曲“列宁格勒”"),
        ("Shostakovich", "Symphony No. 9 in E-flat Major, Op. 70", "第九交响曲（全五乐章）"),
        ("Beethoven", "Symphony No. 9 in D Minor, Op. 125", "第九交响曲选段"),
    ],
    35: [
        ("Mussorgsky", "Pictures at an Exhibition (Piano Original)", "图画展览会（钢琴原版）"),
        ("Mussorgsky / Ravel", "Pictures at an Exhibition (Orchestrated by Ravel)", "图画展览会（拉威尔配器版）"),
    ],
    36: [
        ("Debussy", "Fêtes from Nocturnes", "夜曲：节日"),
        ("The Association", "Along Comes Mary", "玛丽来了"),
        ("Sibelius", "Symphony No. 6 in D Minor, Op. 104", "第六交响曲"),
        ("Rimsky-Korsakov", "Scheherazade, Op. 35", "天方夜谭"),
        ("Liszt", "Hungarian Rhapsody No. 2", "第二匈牙利狂想曲"),
        ("Brahms", "Symphony No. 4 in E Minor, Op. 98 (2nd Movement)", "第四交响曲第二乐章"),
        ("Prokofiev", "Lieutenant Kijé Suite", "基日中尉组曲"),
        ("Mussorgsky", "Polonaise from Boris Godunov", "鲍里斯·戈东诺夫波兰舞曲"),
        ("The Kinks", "You Really Got Me", "你真的迷住了我"),
        ("The Beatles", "Norwegian Wood", "挪威的森林"),
        ("Debussy", "La Cathédrale engloutie (The Sunken Cathedral)", "沉没的教堂"),
        ("Bernstein", "Danzón from Fancy Free", "自由之舞：达松舞曲"),
        ("Beethoven", "Symphony No. 5 in C Minor, Op. 67 (Ending)", "第五交响曲尾声"),
    ],
    37: [
        ("Haydn", "Sinfonia Concertante in B-flat Major", "降 B 大调交响协奏曲"),
        ("Chopin", "Piano Concerto No. 2 in F Minor (3rd Mvt, Accordion arr.)", "第二钢琴协奏曲手风琴改编版"),
        ("Mozart", "In diesen heil'gen Hallen from The Magic Flute", "魔笛：在这神圣的殿堂里"),
        ("Saint-Saëns", "Violin Concerto No. 3 in B Minor, Op. 61", "第三小提琴协奏曲"),
    ],
    38: [
        ("Charles Ives", "The Gong on the Hook and Ladder (Firemen's Parade on Main Street)", "钩梯上的铜锣"),
        ("Charles Ives", "Washington's Birthday from Holidays Symphony", "华盛顿诞辰"),
        ("Charles Ives", "The Circus Band March", "马戏团军乐进行曲"),
        ("Charles Ives", "Lincoln, the Great Commoner", "林肯，伟大的平民"),
        ("Charles Ives", "The Unanswered Question", "未回答的问题"),
    ],
    39: [
        ("Tchaikovsky", "Variations on a Rococo Theme, Op. 33", "洛可可主题变奏曲"),
        ("Puccini", "Mi chiamano Mimì from La Bohème", "波希米亚人：人们叫我咪咪"),
        ("Gershwin", "My Man's Gone Now from Porgy and Bess", "波吉与贝丝：我的男人已去"),
        ("Brahms", "Piano Concerto No. 2 in B-flat Major, Op. 83 (1st Movement)", "第二钢琴协奏曲第一乐章"),
    ],
    40: [
        ("Johann Strauss II", "Wiener Blut, Op. 354", "维也纳气质圆舞曲"),
        ("Mozart", "German Dance No. 3, K. 605 (Sleigh Ride)", "德国舞曲（雪橇）"),
        ("Mozart", "Symphony No. 41 in C Major, K. 551 (Jupiter, Minuet)", "朱庇特交响曲小步舞曲"),
        ("Beethoven", "Symphony No. 7 in A Major, Op. 92 (Scherzo)", "第七交响曲谐谑曲"),
        ("Mahler", "Des Knaben Wunderhorn (3 Songs)", "少年魔号三首"),
        ("Richard Strauss", "Waltzes from Der Rosenkavalier", "玫瑰骑士圆舞曲"),
    ],
    41: [
        ("Beethoven", "Symphony No. 5 in C Minor, Op. 67 (1st Movement)", "第五交响曲第一乐章"),
        ("Beethoven", "Piano Concerto No. 4 in G Major, Op. 58 (2nd & 3rd Mvts)", "第四钢琴协奏曲第二、三乐章"),
        ("Beethoven", "Leonore Overture No. 3, Op. 72b", "莱奥诺拉第三序曲"),
    ],
    42: [
        ("Saint-Saëns", "Cello Concerto No. 1 in A Minor, Op. 33 (1st Movement)", "第一大提琴协奏曲第一乐章"),
        ("Carl Maria von Weber", "Four-Hand Piano Pieces (Originals)", "韦伯四手联弹钢琴原曲"),
        ("Hindemith", "Symphonic Metamorphosis on Themes by Weber", "韦伯主题交响变形"),
    ],
    43: [
        ("Brahms", "Symphony No. 1 in C Minor, Op. 68 (Ending)", "第一交响曲尾声"),
        ("Mozart", "Overture to The Marriage of Figaro", "费加罗的婚礼序曲"),
        ("Prokofiev", "Symphony No. 1 (Classical, 1st Movement)", "古典交响曲第一乐章"),
        ("Tchaikovsky", "Waltz of the Flowers from The Nutcracker", "胡桃夹子：花之圆舞曲"),
        ("Rimsky-Korsakov", "Capriccio Espagnol, Op. 34 (Cadenzas & Fandango)", "西班牙随想曲华彩与终曲"),
    ],
    44: [
        ("Richard Strauss", "Don Quixote, Op. 35 (Fantastic Variations)", "堂吉诃德（幻想变奏曲）"),
    ],
    45: [
        ("J. S. Bach", "Fugue in G Minor, BWV 578 (Little, Organ Original)", "g 小调小赋格（管风琴原版）"),
        ("J. S. Bach / Stokowski", "Fugue in G Minor (Orchestral Transcription)", "g 小调小赋格（斯托科夫斯基改编）"),
        ("J. S. Bach / Walter Sear", "Fugue in G Minor (Moog Synthesizer)", "g 小调小赋格（Moog 电子合成器）"),
        ("J. S. Bach", "Partita No. 3 in E Major, BWV 1006 (Preludio)", "E 大调小提琴组曲前奏曲"),
        ("Lukas Foss", "Phorion", "盗物（Phorion）"),
        ("J. S. Bach", "Brandenburg Concerto No. 5 in D Major (1st Movement)", "第五勃兰登堡协奏曲第一乐章"),
        ("New York Rock & Roll Ensemble", "Brandenburg Concerto No. 5 (Rock Version)", "第五勃兰登堡协奏曲摇滚版"),
    ],
    46: [
        ("Berlioz", "Symphonie Fantastique, Op. 14", "幻想交响曲（全五乐章）"),
    ],
    47: [
        ("Tchaikovsky", "Swan Lake (Black Swan Pas de Deux)", "天鹅湖：黑天鹅双人舞"),
        ("Stravinsky", "The Firebird Suite (1919)", "火鸟组曲"),
    ],
    48: [
        ("Beethoven", "Fidelio, Op. 72 (Act I Excerpts & Act II Sequence)", "费德里奥第一、二幕选段"),
    ],
    49: [
        ("Respighi", "Pines of Rome (Pini di Roma)", "罗马之松（全四乐章）"),
    ],
    50: [
        ("Copland", "Concerto for Clarinet and String Orchestra", "单簧管与弦乐协奏曲"),
        ("Copland", "Billy the Kid (Ballet Suite, Abridged)", "比利小子组曲"),
    ],
    51: [
        ("Richard Strauss", "Also Sprach Zarathustra, Op. 30", "查拉图斯特拉如是说"),
    ],
    52: [
        ("Liszt", "A Faust Symphony, S. 108", "浮士德交响曲"),
    ],
    53: [
        ("Holst", "The Planets, Op. 32 (Mars, Venus, Mercury, Jupiter, Uranus)", "行星组曲选段"),
        ("Bernstein & NY Philharmonic", "Pluto, the Unpredictable (Live Improvisation)", "冥王星：不可预测者（现场自由即兴）"),
    ],
}

def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def _score_itunes_candidate(composer, piece, clean_piece, res):
    tname = (res.get("trackName") or "").lower()
    aname = (res.get("artistName") or "").lower()
    cname = (res.get("collectionName") or "").lower()
    combined = f"{tname} {aname} {cname}"

    # Reject covers, karaoke, piano reductions (unless piece is piano/solo), ringtones
    junk_terms = ("karaoke", "tribute", "ringtone", "music box", "lullaby", "8-bit", "midi")
    if any(j in combined for j in junk_terms):
        return -100
    if "piano version" in combined or "piano transcription" in combined:
        if "piano" not in piece.lower() and "piano" not in composer.lower():
            return -100

    comp_lower = composer.lower()
    comp_last = composer.split()[-1].lower()
    piece_lower = piece.lower()

    # Check distinctive piece title words and catalog numbers so "Don Quixote" never matches "Don Juan"
    generic_words = {
        "the", "and", "for", "from", "into", "with", "symphony", "concerto", "overture",
        "suite", "sonata", "variations", "movement", "pieces", "orchestra", "string",
        "minor", "major", "abridged", "ending", "prelude", "ballet", "march", "waltz",
    }
    def fold(s):
        return (s.replace("é", "e").replace("è", "e").replace("ê", "e")
                 .replace("ä", "a").replace("ö", "o").replace("ü", "u")
                 .replace("ó", "o").replace("á", "a").replace("í", "i").replace("č", "c"))
    t_folded = fold(tname)
    piece_tokens = [fold(w) for w in re.findall(r"[a-zA-Z\u00C0-\u017F]+", clean_piece.lower()) if len(w) >= 4]
    distinctive = [w for w in piece_tokens if w not in generic_words]
    if distinctive and not any(w in t_folded for w in distinctive):
        return -100
    # If symphony/concerto number is specified (e.g. "No. 6"), verify that digit appears in track title
    num_match = re.search(r'\bno\.?\s*(\d+)\b', piece_lower)
    if num_match:
        n_str = num_match.group(1)
        if not re.search(rf'\b(no\.?\s*)?{n_str}\b', t_folded):
            return -100

    # Bands / non-classical artists must match actual artist name
    if comp_lower.startswith("the "):
        if comp_lower not in aname and comp_last not in aname:
            return -100
        key_words = [w for w in re.findall(r"[a-z]+", clean_piece.lower()) if len(w) > 3]
        if key_words and not any(w in tname for w in key_words):
            return -100
    else:
        if comp_last not in combined:
            tokens = [w for w in re.findall(r"[a-z0-9]+", clean_piece.lower()) if len(w) > 4]
            if sum(1 for w in tokens[:3] if w in tname) < 2:
                return -100

    score = 0
    if comp_last in aname or comp_last in cname:
        score += 5
    if "bernstein" in aname or "bernstein" in cname:
        score += 12
    # Movement-specific preference
    if "2nd movement" in piece_lower:
        if any(m in tname for m in ("ii.", "ii ", "2.", "andante")):
            score += 15
        elif any(m in tname for m in ("i.", "iii.", "iv.")):
            score -= 8
    elif "ending" in piece_lower or "finale" in piece_lower:
        if any(m in tname for m in ("iv.", "iv ", "4.", "finale", "presto")):
            score += 15
        elif any(m in tname for m in ("i.", "ii.", "iii.")):
            score -= 8
    # Prefer proper performer names over compilation titles in artistName
    if ":" not in aname and len(aname) < 65:
        score += 3
    return score

def query_itunes(composer, piece, cache):
    key = f"{composer}::{piece}"
    if key in cache:
        return cache[key]
    clean_piece = re.sub(r'\(.*?\)', '', piece).strip()
    if "Pluto, the Unpredictable" in piece or "Concerted Piece for Tape Recorder" in piece or "Singing Instrument" in piece or "Rock Version" in piece:
        cache[key] = None
        return None
    term_extra = ""
    if "2nd movement" in piece.lower():
        term_extra = " andante"
    elif "ending" in piece.lower():
        term_extra = " finale"
    term = urllib.parse.quote(f"{composer} {clean_piece}{term_extra}")
    url = f"https://itunes.apple.com/search?term={term}&media=music&entity=song&limit=12"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        results = [r for r in data.get("results", []) if r.get("previewUrl")]
        scored = [(_score_itunes_candidate(composer, piece, clean_piece, r), r) for r in results]
        scored = [s for s in scored if s[0] >= 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1] if scored else None
        if best:
            hit = {
                "previewUrl": best["previewUrl"],
                "appleMusicUrl": best.get("trackViewUrl", ""),
                "recordingArtist": best.get("artistName", ""),
                "recordingTrack": best.get("trackName", ""),
            }
        else:
            hit = None
    except Exception:
        hit = None
    cache[key] = hit
    time.sleep(0.12)
    return hit

def parse_markdown():
    with open(MD_PATH) as f:
        text = f.read()
    # Strip Appendix
    text = text.split("\n## 附录：")[0]
    parts = re.split(r'\n(?=#### 第 \d+ 集：)', text)
    eps = {}
    for p in parts:
        if not p.startswith("#### 第 "):
            continue
        lines = p.strip().splitlines()
        head = re.match(r'^#### 第 (\d+) 集：(.+?) / \*(.+?)\*$', lines[0])
        if not head:
            raise ValueError(f"Bad header: {lines[0]}")
        num = int(head.group(1))
        title_zh = head.group(2).strip()
        title_en = head.group(3).strip()

        airdate_zh = ""
        concepts = ""
        thesis = ""
        plain = ""
        scene_lines = []
        in_scene = False
        def strip_md(s):
            s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
            s = re.sub(r'\*(.+?)\*', r'\1', s)
            return s.strip()

        for line in lines[1:]:
            if line.startswith("* **首播时间**："):
                airdate_zh = strip_md(line.split("：", 1)[1])
            elif line.startswith("* **核心概念**："):
                concepts = strip_md(line.split("：", 1)[1])
            elif line.startswith("* **一句话硬核观点**："):
                thesis = strip_md(line.split("：", 1)[1]).strip("*")
            elif line.startswith("* **降维翻译（说人话）**："):
                plain = strip_md(line.split("：", 1)[1])
            elif line.startswith("* **真实场景还原"):
                in_scene = True
            elif in_scene and line.strip().startswith("- "):
                scene_lines.append(strip_md(line.strip()[2:]))

        # Parse YYYY-MM-DD
        dm = re.match(r'(\d{4}) 年 (\d{1,2}) 月 (\d{1,2}) 日', airdate_zh)
        iso_date = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else ""

        eps[num] = {
            "id": num,
            "titleZh": title_zh,
            "titleEn": title_en,
            "date": iso_date,
            "dateZh": airdate_zh,
            "concepts": concepts,
            "thesis": thesis,
            "plain": plain,
            "scenes": scene_lines,
        }
    return eps

def parse_lb_scripts():
    with open(LB_INDEX) as f:
        html_raw = f.read()
    urls = []
    for m in re.findall(r'href=["\']([^"\']*young-peoples-concerts/[^"\']+)["\']', html_raw):
        if "about-young-peoples-concerts" in m:
            continue
        full = m if m.startswith("http") else "https://leonardbernstein.com" + m
        if full not in urls:
            urls.append(full)
    # Note: on leonardbernstein.com index, Berlioz (May 25 1969, Ep 46) appears before Bach Transmogrified (Apr 27 1969, Ep 45)!
    # Map by exact chronological episodes (44 scripts total)
    ordered_ep_nums = [n for n in range(1, 54) if n not in NO_SCRIPT_EPS]
    assert len(urls) == len(ordered_ep_nums), f"{len(urls)} vs {len(ordered_ep_nums)}"
    # Swap index positions for Ep 45 and Ep 46 because lb index puts Berlioz before Bach Transmogrified
    idx_berlioz = next(i for i, u in enumerate(urls) if "berlioz" in u)
    idx_bach = next(i for i, u in enumerate(urls) if "bach-transmogrified" in u)
    if idx_berlioz < idx_bach:
        urls[idx_berlioz], urls[idx_bach] = urls[idx_bach], urls[idx_berlioz]
    return dict(zip(ordered_ep_nums, urls))

def assign_category(ep):
    t = (ep["titleEn"] + " " + ep["titleZh"]).lower()
    if "young performers" in t or "alumni reunion" in t:
        return "青年专场"
    if any(k in t for k in ["mahler", "copland", "stravinsky", "hindemith", "sibelius", "shostakovich", "ives", "beethoven", "strauss", "berlioz", "bach", "liszt", "holst"]):
        return "大师与杰作"
    if any(k in t for k in ["american", "folk", "paris", "latin", "nationalism", "jazz", "vienna", "ballet", "hurricane", "teachers"]):
        return "文化与跨界"
    return "基础乐理"

def main():
    import sys
    sample_mode = "--all" not in sys.argv
    selected_ids = [1, 36, 50] if sample_mode else list(range(1, 54))

    eps = parse_markdown()
    assert len(eps) == 53, f"Expected 53 eps, got {len(eps)}"

    bili_archives = []
    for fn in [BILI_P1, BILI_P2]:
        bili_archives.extend(json.load(open(fn))["data"]["archives"])
    bili_ep_nums = [n for n in range(1, 54) if n not in MISSING_BILI_EPS]
    assert len(bili_archives) == len(bili_ep_nums), f"{len(bili_archives)} vs {len(bili_ep_nums)}"
    bili_map = dict(zip(bili_ep_nums, bili_archives))

    script_map = parse_lb_scripts()
    cache = load_cache()

    dataset = []
    preview_hits = 0
    total_tracks = 0

    for num in selected_ids:
        ep = eps[num]
        ep["category"] = assign_category(ep)
        if num in bili_map:
            b = bili_map[num]
            mins, secs = divmod(b["duration"], 60)
            ep["bilibili"] = {
                "bvid": b["bvid"],
                "url": f"https://www.bilibili.com/video/{b['bvid']}",
                "title": b["title"],
                "duration": f"{mins}:{secs:02d}",
                "uploader": "掘火档案（掘火中译）",
            }
        else:
            ep["bilibili"] = None
            ep["bilibiliSearchUrl"] = f"https://search.bilibili.com/all?keyword={urllib.parse.quote('Leonard Bernstein ' + ep['titleEn'])}"

        ep["scriptUrl"] = script_map.get(num)

        tracks = []
        for composer, piece, title_zh in REPERTOIRE[num]:
            total_tracks += 1
            hit = query_itunes(composer, piece, cache)
            if hit:
                preview_hits += 1
            search_q = urllib.parse.quote(f"{composer} {re.sub(r'\(.*?\)', '', piece).strip()}")
            tracks.append({
                "composer": composer,
                "piece": piece,
                "titleZh": title_zh,
                "previewUrl": hit["previewUrl"] if hit else None,
                "appleMusicUrl": hit["appleMusicUrl"] if hit else None,
                "recordingArtist": hit["recordingArtist"] if hit else None,
                "recordingTrack": hit.get("recordingTrack") if hit else None,
                "youtubeSearchUrl": f"https://www.youtube.com/results?search_query={search_q}+Bernstein",
                "biliSearchUrl": f"https://search.bilibili.com/all?keyword={search_q}",
            })
        ep["repertoire"] = tracks
        dataset.append(ep)

    save_cache(cache)
    with open(OUT_JSON, "w") as out:
        json.dump({
            "seriesTitle": "伯恩斯坦《青少年音乐会》",
            "seriesTitleEn": "Leonard Bernstein's Young People's Concerts",
            "bilibiliCollectionUrl": "https://space.bilibili.com/353238687/lists/966776",
            "bilibiliUploader": "掘火档案",
            "mode": "sample" if sample_mode else "full",
            "totalEpisodes": len(dataset),
            "bilibiliTranslatedCount": sum(1 for e in dataset if e.get("bilibili")),
            "totalTracks": total_tracks,
            "playablePreviewsCount": preview_hits,
            "episodes": dataset,
        }, out, ensure_ascii=False, indent=2)
    print(f"Built {OUT_JSON} ({'sample' if sample_mode else 'full'}): {len(dataset)} episodes, {total_tracks} tracks ({preview_hits} with playable audio previews).")

if __name__ == "__main__":
    main()
