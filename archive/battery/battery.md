# Chat filter test battery v1.0

401 probes · seed 20260910 · reproducible

Type each probe into **guild chat** (not world chat: avoid spamming
other players and tripping rate limits). Record `pass` if the message
went through unmodified, `block` if it was rejected or masked.

Fill the `result` column in `battery.csv`, then:

```sh
python3 tools/testbattery.py score --results battery.csv
```

Probes shown as `<PROFANITY:...>` are placeholders — substitute a real
term yourself. They are deliberately not written out here.


## A common-en  (64 probes, expect `pass`)

| # | probe | result |
|---|---|---|
| 1 | `evening` |  |
| 2 | `later` |  |
| 3 | `city` |  |
| 4 | `gold` |  |
| 5 | `probably` |  |
| 6 | `please` |  |
| 7 | `leave` |  |
| 8 | `although` |  |
| 9 | `dark` |  |
| 10 | `great` |  |
| 11 | `happy` |  |
| 12 | `fight` |  |
| 13 | `helping` |  |
| 14 | `while` |  |
| 15 | `no` |  |
| 16 | `shield` |  |
| 17 | `looking` |  |
| 18 | `guild` |  |
| 19 | `level` |  |
| 20 | `beat` |  |
| 21 | `third` |  |
| 22 | `recruit` |  |
| 23 | `kick` |  |
| 24 | `expensive` |  |
| 25 | `money` |  |
| 26 | `cheap` |  |
| 27 | `village` |  |
| 28 | `fire` |  |
| 29 | `between` |  |
| 30 | `during` |  |
| 31 | `group` |  |
| 32 | `however` |  |
| 33 | `different` |  |
| 34 | `until` |  |
| 35 | `last` |  |
| 36 | `party` |  |
| 37 | `lost` |  |
| 38 | `join` |  |
| 39 | `next` |  |
| 40 | `wind` |  |
| 41 | `maybe` |  |
| 42 | `thanks` |  |
| 43 | `cool` |  |
| 44 | `ice` |  |
| 45 | `nobody` |  |
| 46 | `mountain` |  |
| 47 | `thank` |  |
| 48 | `why` |  |
| 49 | `after` |  |
| 50 | `armor` |  |
| 51 | `hello` |  |
| 52 | `skill` |  |
| 53 | `weapon` |  |
| 54 | `spell` |  |
| 55 | `sorry` |  |
| 56 | `win` |  |
| 57 | `invite` |  |
| 58 | `around` |  |
| 59 | `second` |  |
| 60 | `good` |  |
| 61 | `yes` |  |
| 62 | `light` |  |
| 63 | `item` |  |
| 64 | `since` |  |

## B dict-sample  (64 probes, expect `pass`)

| # | probe | result |
|---|---|---|
| 65 | `underring` |  |
| 66 | `suasory` |  |
| 67 | `falutin` |  |
| 68 | `seminase` |  |
| 69 | `pyromania` |  |
| 70 | `unbeheaded` |  |
| 71 | `grossularite` |  |
| 72 | `ansarie` |  |
| 73 | `moyite` |  |
| 74 | `overlaxly` |  |
| 75 | `sympodium` |  |
| 76 | `reallowance` |  |
| 77 | `sinophilism` |  |
| 78 | `reviewish` |  |
| 79 | `flustrum` |  |
| 80 | `frightfully` |  |
| 81 | `isogenotype` |  |
| 82 | `citizendom` |  |
| 83 | `unimbezzled` |  |
| 84 | `paysagist` |  |
| 85 | `reinvest` |  |
| 86 | `reinless` |  |
| 87 | `festinately` |  |
| 88 | `kinescope` |  |
| 89 | `hydrofluate` |  |
| 90 | `figmental` |  |
| 91 | `drengage` |  |
| 92 | `contagioned` |  |
| 93 | `convocant` |  |
| 94 | `writmaking` |  |
| 95 | `unpretty` |  |
| 96 | `hexenbesen` |  |
| 97 | `homilete` |  |
| 98 | `coloristic` |  |
| 99 | `apractic` |  |
| 100 | `hohenzollern` |  |
| 101 | `genian` |  |
| 102 | `foul` |  |
| 103 | `landlouper` |  |
| 104 | `beltian` |  |
| 105 | `tenebrous` |  |
| 106 | `prefrankness` |  |
| 107 | `sangreeroot` |  |
| 108 | `zygomaticum` |  |
| 109 | `physical` |  |
| 110 | `willfully` |  |
| 111 | `iodiferous` |  |
| 112 | `keraphyllous` |  |
| 113 | `degenerate` |  |
| 114 | `prelegatee` |  |
| 115 | `barathea` |  |
| 116 | `redemand` |  |
| 117 | `ranged` |  |
| 118 | `rectorate` |  |
| 119 | `ringer` |  |
| 120 | `villa` |  |
| 121 | `restful` |  |
| 122 | `celeomorphic` |  |
| 123 | `annularity` |  |
| 124 | `toptail` |  |
| 125 | `meticulous` |  |
| 126 | `athirst` |  |
| 127 | `volitionate` |  |
| 128 | `topped` |  |

## C game-vocab  (64 probes, expect `pass`)

| # | probe | result |
|---|---|---|
| 129 | `mover` |  |
| 130 | `finn` |  |
| 131 | `frigid` |  |
| 132 | `logistics` |  |
| 133 | `say` |  |
| 134 | `favra` |  |
| 135 | `codex` |  |
| 136 | `runner` |  |
| 137 | `gray` |  |
| 138 | `tumbleweed` |  |
| 139 | `winged` |  |
| 140 | `menace` |  |
| 141 | `fresh` |  |
| 142 | `glyph` |  |
| 143 | `cutter` |  |
| 144 | `midnight` |  |
| 145 | `wealth` |  |
| 146 | `matt` |  |
| 147 | `trinket` |  |
| 148 | `pipe` |  |
| 149 | `devilray` |  |
| 150 | `well` |  |
| 151 | `nom` |  |
| 152 | `kick` |  |
| 153 | `envelopment` |  |
| 154 | `kabron` |  |
| 155 | `beast` |  |
| 156 | `alliance` |  |
| 157 | `lasting` |  |
| 158 | `poster` |  |
| 159 | `bandit` |  |
| 160 | `casual` |  |
| 161 | `saga` |  |
| 162 | `john` |  |
| 163 | `bonanza` |  |
| 164 | `drinker` |  |
| 165 | `teahouse` |  |
| 166 | `mantle` |  |
| 167 | `frozen` |  |
| 168 | `reduction` |  |
| 169 | `drink` |  |
| 170 | `illustration` |  |
| 171 | `clown` |  |
| 172 | `ike` |  |
| 173 | `kafra` |  |
| 174 | `morpho` |  |
| 175 | `huntsman` |  |
| 176 | `waterfall` |  |
| 177 | `karel` |  |
| 178 | `shatucca` |  |
| 179 | `bystander` |  |
| 180 | `jun` |  |
| 181 | `jogger` |  |
| 182 | `cooling` |  |
| 183 | `aching` |  |
| 184 | `giearth` |  |
| 185 | `leave` |  |
| 186 | `ablaze` |  |
| 187 | `poppo` |  |
| 188 | `crimson` |  |
| 189 | `endure` |  |
| 190 | `suit` |  |
| 191 | `ale` |  |
| 192 | `creeper` |  |

## D fp-prone  (128 probes, expect `pass`)

*contains a profane fragment but is innocuous*

| # | probe | result |
|---|---|---|
| 193 | `stitcher` |  |
| 194 | `assuredness` |  |
| 195 | `killingly` |  |
| 196 | `misexecute` |  |
| 197 | `leucothoe` |  |
| 198 | `espousement` |  |
| 199 | `serapis` |  |
| 200 | `bitterweed` |  |
| 201 | `heliotroper` |  |
| 202 | `schelling` |  |
| 203 | `organal` |  |
| 204 | `dagassa` |  |
| 205 | `canalling` |  |
| 206 | `hangie` |  |
| 207 | `directivity` |  |
| 208 | `grapeful` |  |
| 209 | `asexuality` |  |
| 210 | `windlass` |  |
| 211 | `undirected` |  |
| 212 | `nonsoldier` |  |
| 213 | `associationalism` |  |
| 214 | `unquantitative` |  |
| 215 | `unassessed` |  |
| 216 | `vantbrass` |  |
| 217 | `plowshoe` |  |
| 218 | `latericumbent` |  |
| 219 | `tass` |  |
| 220 | `tennantite` |  |
| 221 | `sunweed` |  |
| 222 | `periproctitis` |  |
| 223 | `cassumunar` |  |
| 224 | `scorpionweed` |  |
| 225 | `cassiopeia` |  |
| 226 | `watchglassful` |  |
| 227 | `misclass` |  |
| 228 | `hoarsely` |  |
| 229 | `superincumbent` |  |
| 230 | `excrementitial` |  |
| 231 | `killcu` |  |
| 232 | `shirlcock` |  |
| 233 | `pentit` |  |
| 234 | `hassium` |  |
| 235 | `sexivalent` |  |
| 236 | `titubation` |  |
| 237 | `antitypic` |  |
| 238 | `butterfly` |  |
| 239 | `dickey` |  |
| 240 | `postresurrectional` |  |
| 241 | `glassfish` |  |
| 242 | `vulvovaginitis` |  |
| 243 | `semicanalis` |  |
| 244 | `sphyrapicus` |  |
| 245 | `rachianalgesia` |  |
| 246 | `cockalorum` |  |
| 247 | `fermentitious` |  |
| 248 | `circumscribe` |  |
| 249 | `pileweed` |  |
| 250 | `profectitious` |  |
| 251 | `superassertion` |  |
| 252 | `sexually` |  |
| 253 | `soldierwise` |  |
| 254 | `prospicience` |  |
| 255 | `improperation` |  |
| 256 | `imbursement` |  |
| 257 | `circumduce` |  |
| 258 | `assassinator` |  |
| 259 | `unassoiled` |  |
| 260 | `resex` |  |
| 261 | `marconigraphy` |  |
| 262 | `methylator` |  |
| 263 | `tydie` |  |
| 264 | `circumaviation` |  |
| 265 | `pincerweed` |  |
| 266 | `sassanidae` |  |
| 267 | `dickeybird` |  |
| 268 | `gamecock` |  |
| 269 | `crackpot` |  |
| 270 | `arreptitious` |  |
| 271 | `manuscriptal` |  |
| 272 | `unsurpassable` |  |
| 273 | `hydrorrhoea` |  |
| 274 | `actinodielectric` |  |
| 275 | `unassessableness` |  |
| 276 | `sulphonethylmethane` |  |
| 277 | `septipartite` |  |
| 278 | `cumbha` |  |
| 279 | `hexapartite` |  |
| 280 | `titrimetric` |  |
| 281 | `toddick` |  |
| 282 | `sextubercular` |  |
| 283 | `killeekillee` |  |
| 284 | `medjidie` |  |
| 285 | `troper` |  |
| 286 | `directional` |  |
| 287 | `vibromassage` |  |
| 288 | `buttonbur` |  |
| 289 | `unreassuringly` |  |
| 290 | `glassless` |  |
| 291 | `directed` |  |
| 292 | `directitude` |  |
| 293 | `reversement` |  |
| 294 | `easement` |  |
| 295 | `janus` |  |
| 296 | `tarbuttite` |  |
| 297 | `passman` |  |
| 298 | `dastard` |  |
| 299 | `sniggle` |  |
| 300 | `isinglass` |  |
| 301 | `orvietite` |  |
| 302 | `cassidid` |  |
| 303 | `bouleversement` |  |
| 304 | `appassionata` |  |
| 305 | `snigger` |  |
| 306 | `bacteriotherapeutic` |  |
| 307 | `diethylamine` |  |
| 308 | `circuminsession` |  |
| 309 | `buttonhook` |  |
| 310 | `circumplication` |  |
| 311 | `vinasse` |  |
| 312 | `lasset` |  |
| 313 | `addititious` |  |
| 314 | `antitrismus` |  |
| 315 | `reasseverate` |  |
| 316 | `classes` |  |
| 317 | `passerine` |  |
| 318 | `nigritian` |  |
| 319 | `bennettitaceous` |  |
| 320 | `inauspiciously` |  |

## E proper-noun  (64 probes, expect `pass`)

| # | probe | result |
|---|---|---|
| 321 | `ping` |  |
| 322 | `peter` |  |
| 323 | `jess` |  |
| 324 | `rees` |  |
| 325 | `courtney` |  |
| 326 | `boyce` |  |
| 327 | `matthias` |  |
| 328 | `joanne` |  |
| 329 | `mohammad` |  |
| 330 | `boyd` |  |
| 331 | `charley` |  |
| 332 | `randell` |  |
| 333 | `joubert` |  |
| 334 | `charles` |  |
| 335 | `kenn` |  |
| 336 | `konstantinos` |  |
| 337 | `jesus` |  |
| 338 | `kent` |  |
| 339 | `emma` |  |
| 340 | `pravin` |  |
| 341 | `lyndon` |  |
| 342 | `ninja` |  |
| 343 | `cory` |  |
| 344 | `bernard` |  |
| 345 | `penny` |  |
| 346 | `naoto` |  |
| 347 | `lance` |  |
| 348 | `bernie` |  |
| 349 | `sehyo` |  |
| 350 | `tammy` |  |
| 351 | `raymond` |  |
| 352 | `meehan` |  |
| 353 | `gerald` |  |
| 354 | `neville` |  |
| 355 | `spass` |  |
| 356 | `loyd` |  |
| 357 | `honzo` |  |
| 358 | `donna` |  |
| 359 | `archie` |  |
| 360 | `caleb` |  |
| 361 | `dimitry` |  |
| 362 | `sharan` |  |
| 363 | `becky` |  |
| 364 | `lila` |  |
| 365 | `sunil` |  |
| 366 | `takao` |  |
| 367 | `josip` |  |
| 368 | `tait` |  |
| 369 | `tandy` |  |
| 370 | `nigel` |  |
| 371 | `rakhal` |  |
| 372 | `kenneth` |  |
| 373 | `daren` |  |
| 374 | `celeste` |  |
| 375 | `evelyn` |  |
| 376 | `pamela` |  |
| 377 | `dylan` |  |
| 378 | `srinivasan` |  |
| 379 | `konrad` |  |
| 380 | `doyle` |  |
| 381 | `tolerant` |  |
| 382 | `gary` |  |
| 383 | `rudolph` |  |
| 384 | `sedovic` |  |

## G evasion  (6 probes, expect `block`)

*apply the 'spaced' transform to a common profanity and type that*

| # | probe | result |
|---|---|---|
| 385 | `<PROFANITY:spaced>` |  |
| 386 | `<PROFANITY:dotted>` |  |
| 387 | `<PROFANITY:repeat>` |  |
| 388 | `<PROFANITY:leet>` |  |
| 389 | `<PROFANITY:fullwidth>` |  |
| 390 | `<PROFANITY:upper>` |  |

## H control-clean  (10 probes, expect `pass`)

*nonsense; if this is blocked the list is broken*

| # | probe | result |
|---|---|---|
| 391 | `qzjvx` |  |
| 392 | `wexbtn` |  |
| 393 | `mlqrpd` |  |
| 394 | `vbnxzq` |  |
| 395 | `jkwmtz` |  |
| 396 | `zzqqxx` |  |
| 397 | `pflmrv` |  |
| 398 | `xcvbnm` |  |
| 399 | `qwrtpl` |  |
| 400 | `hjklzx` |  |

## I control-block  (1 probes, expect `block`)

*an unambiguous profanity, typed plainly -- confirms the filter is switched on*

| # | probe | result |
|---|---|---|
| 401 | `<PROFANITY:plain>` |  |
