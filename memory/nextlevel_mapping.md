# NextLevel Delivery — как приема пратките (измерено, не предположено)

Източник: официалната документация (nextlevel-delivery.readme.io) + ~120 реални заявки към
`POST /v1/shipments/calculate` с ключовете на PurePeptide (не създава пратки) + анализ на последните
реални пратки на акаунта (sender **#594 „Пюр Пептид ЕООД“**, офис 1 = NextLevel HUB).
Сурови резултати: `nextlevel_probe.json`, `nextlevel_probe2.txt`, `nextlevel_probe3.txt`,
`nextlevel_real_usage.txt`.

## Достъп
- База: `https://api.nextlevel.delivery/v1`, хедъри `app-id` + `app-secret` (нашите ключове работят).
- Създаване: `POST /shipments` → връща `awb` (13 цифри, напр. 1000030718981), `courier_awb`, `tracking_link`.
- Цена без създаване: `POST /shipments/calculate`. Печат: `POST /shipments/print/{awb}` (PDF, A6 за
  този акаунт). Следене: `POST /shipments/track {awbs:[…]}`. Отказ: `POST /shipments/cancel`.
- Офиси/автомати: `GET /offices?country=BG&courier=Econt&search=…` → `id` (вътрешен, ползва се в
  `receiver.office_id`), `office_code` (кодът на куриера), `is_machine` (автомат).
- **NextCart/RevOrder офисите в нашия чекаут са същите**: `"id": "econt:4434"` ⇒ NextLevel `office_id=4434`,
  `"code": "9040"` ⇒ `office_code`. Директно съответствие, без търсене.

## Тяло на пратка (както ги прави магазинът днес през Shopify)
```json
{
  "sender": {"id": 594, "office_id": 1},
  "receiver": {"name": "…", "phone": "+359…", "email": "…", "office_id": 4434},      // офис/автомат
  // или адрес:  {"country":"BG","place":"София","post_code":"1000","street":"бул. Витоша","street_no":"1"}
  "content": {"parcels_count": 1, "weight": 0.4, "package": "PACK", "contents": "<номер на поръчка>"},
  "payment": {"payer": "sender"},
  "ref": "<номер на поръчка>", "ref2": "<id на поръчка>",
  "services": {"cod": {"amount": 91.99, "currency": "EUR", "processing_type": "CASH", "included_shipping_price": false}}
}
```
Реалните пратки досега: тегло винаги **0.4 kg**, `ref` = номер на поръчката (01046442), `ref2`/`content` =
Shopify id, COD **CASH**, `included_shipping_price:false`, без `courier` (определя се от офиса/страната).

## Правила, потвърдени с тестове
| Правило | Резултат |
|---|---|
| `weight` задължително; приема и низ "0.5" | без него → 400 |
| Цена по тегло (Econt BG адрес) | 0.01–1 kg = 4.70 €, 3 kg = 7.42, 10 kg = 11.40, 31 kg = 19.17, 50 kg = 26.19 (няма горен лимит до 50) |
| Адрес: `post_code` задължителен | без него → 400 („receiver.post code field is required“) — **село без пощенски код се отхвърля** |
| Адрес: `street` НЕ е задължителен за калкулация | приема само place + post_code; приема и свободен текст в `address` |
| Град на латиница („Sofia“) | приема се |
| Грешен пощенски код (9999) | приема се (не валидира) |
| Държава малки букви („bg“) | приема се; „XX“ → 400 |
| `sender.office_id` може да липсва | приема се (default 1) |
| Грешен sender id | 400 „Invalid sender ID“ |
| COD: `included_shipping_price` **задължително** | без него → 400; `true` → 400 „You don't have permission“ → винаги `false` |
| COD: `processing_type` задължително | CASH или BANK (еднаква такса) |
| COD валута | трябва да е валутата на държавата: BG/GR/DE/SK/SI/HR/IT/AT… = **EUR**, RO = **RON**, HU = **HUF**, PL = **PLN**, CZ = **CZK**; „BGN“ → 400 |
| COD в грешна валута (напр. EUR за RO) | **НЕ дава грешка** — приема се и таксува като EUR → трябва да го пазим ние |
| COD такса | BG 1.5 % (мин. 0.94 € при 62.89), RO 1.5 %, HU/PL/CZ 2 % **върху голото число** (25 990 HUF → такса „519.80“!) — да се провери с account manager-а, вероятно грешно ценообразуване в calculate |
| `card_cod` | приема се без такса (алтернатива на COD с карта) |
| `dv` (обявена стойност), `fragile`, `sd`, `obpd`, `signature` | приемат се, без допълнителна такса в calculate |
| `office_code` вместо `office_id` | работи само заедно с `country` + `place` + `post_code` (иначе 400) → **ползваме `office_id`** |

## Куриери по държави (какво реално е активирано за акаунта)
| Държава | Работи (адрес) | Работи (офис/автомат) | НЕ е активирано („does not have setup for this courier“) | Цена 0.5 kg / COD |
|---|---|---|---|---|
| **BG** | auto=Econt 4.70 €, Sameday 4.24 €, Speedy „0.00“*, PigeonExpress (реални пратки) | Econt офис 3.99 € + 41 еконтомата; BoxNow 927 автомата („0.00“*, реално 1.90 €); Speedy 1000 офиса/544 автомата „0.00“*; Sameday easybox 1000 „0.00“* | — | COD +0.94 € (1.5 %) |
| **RO** | auto=FAN 3.78 € | FAN 445 офиса 3.78 € | Speedy, DPD, Sameday easybox (RO) | COD RON 1.5 % |
| **GR** | auto=Geniki 8.81 €, ACS 8.41, Speedex 8.51 | ACS 486, Speedex 211, Geniki 221, **BoxNow 1000 автомата 4.80 €** | Speedy, CourierGr | COD +1.28–1.57 € |
| **HU** | auto=GLS 5.36 € | GLS 458 | Sprinter | COD HUF (такса 2 % — виж бележката) |
| **PL** | auto 5.36 € (без име) | Speedy офисите → грешка | Speedy | COD PLN 2 % |
| **CZ** | auto 5.85 € | Speedy офисите → грешка | Speedy | COD CZK 2 % |
| **SK** | auto=GLS 5.36 € | GLS 428 | Speedy | COD 1.26 € |
| **SI** | auto=GLS 5.46 € | GLS 853 | Speedy | COD 1.26 € |
| **HR** | auto 34.45 € (!) | — | Overseas, Speedy | COD 1.26 € |
| **DE** | GLS 5.65 € | GLS 1000 „офиси“ | — | COD +5.11 € (фикс) |
| **IT** | auto 24.92 € | — | GLS по име → грешка (само auto) | COD +3.58 € |
| **AT/NL/BE** | auto 9.20 € | — | — | COD такса 0 → **вероятно COD не се изпълнява** |
| **FR** | auto 10.40 € | — | — | COD 0 → същото |
| **ES** | auto 20.25 € (реална GLS пратка към ES съществува) | — | — | COD 0 |

\* „0.00“ в calculate = за този куриер акаунтът няма ценова листа в калкулатора; реалните пратки към
BoxNow/Speedy BG обаче се създават и се таксуват после (BoxNow 1.90 € базова). Не е грешка, но цената
не може да се покаже предварително.

## Изводи за нашата интеграция
1. **Не подавай `courier`** — офисът (`office_id`) го определя, а за адрес „auto“ работи във всяка държава
   и не удря неактивирани куриери (RO Speedy/DPD, PL/CZ Speedy, IT GLS по име → 400).
2. Офис/автомат: `receiver.office_id = int(nextcart_office_id.split(":")[1])`.
3. Адрес: `country`, `place`, `post_code` (задължително — при липса да не пращаме, а да маркираме
   поръчката „нужен пощенски код“), `street` = ред 1 на адреса, `other` = бележка.
4. COD само при `payment_method == cod`: `amount` = `total_orig` във валутата на държавата (RO→RON,
   HU→HUF, PL→PLN, CZ→CZK), иначе `total_eur`; `processing_type: CASH`, `included_shipping_price: false`.
   Валутата **да се валидира при нас** (NextLevel мълчаливо приема грешна).
5. `content.weight` 0.4 kg за 1–3 флакона (както досега), `package: PACK`, `parcels_count: 1`,
   `contents`/`ref` = номер на поръчката, `ref2` = вътрешен id. `payment.payer: sender`.
6. Съхраняваме `awb`, `courier_awb`, `tracking_link`, статус; печат на етикет през `print/{awb}`;
   `track` на всеки 30 мин за статусите (In Office / In Courier / In parcelshop / In locker / Delivered / Return created…).
7. Да се уточни с NextLevel: COD в HU/PL/CZ (таксата в калкулатора изглежда в EUR върху сумата в
   местна валута) и COD в AT/NL/BE/FR/ES (такса 0 — приема ли се реално).

## Реални тестове (създадени и веднага отказани, 2026-06)
| Случай | Резултат |
|---|---|
| Econt офис / еконтомат / адрес (BG, COD 62.89 €) | ✅ awb 10000308010xx, Econt courier awb 1055…, етикет A6 PDF (65 KB) с „НП: 62.89€ (събери)“ |
| Speedy офис (BG) | ✅ създава се (Speedy) |
| BoxNow автомат (BG) | ✅ |
| Sameday easybox (BG) | ✅ |
| Банков превод (без COD) | ✅ без services |
| FAN Румъния офис + адрес, COD 319 RON | ✅ (FAN) |
| RO с поръчка в EUR (COD валута ≠ RON) | ❌ спряно от нас преди изпращане („трябва да е в RON“) |
| GLS Унгария офис | ❌ NextLevel: „Invalid service PSD“ — доставка до GLS ParcelShop в HU **не е активирана** за акаунта → само адрес |
| GLS Унгария адрес с BG телефон | ❌ GLS: „telephone number wrong“ — за HU трябва унгарски номер на получателя |
| PL / CZ адрес с COD 249 PLN / 1299 CZK | ✅ през GLS; `price.cod` = EUR еквивалент (56.33 €), `native_cod` = 249 → **COD в местна валута се конвертира правилно** (грешката е само в calculate) |
| GLS Германия адрес (без COD) | ✅ |
| ACS Гърция офис, BoxNow Гърция автомат (COD EUR) | ✅ |
| Адрес без пощенски код | ❌ спряно от нас („изисква … пощенски код“) |
| Печат | `POST /shipments/{awb}/print` → PDF · Отказ: `POST /shipments/{awb}/cancel` → `{success:true}` · Track: `POST /shipments/track {ids:[awb…]}` |
| Отговор при създаване | `awb`, `courier_awb`, `subcontractor`, `status` „In sender“, `total_price`, `base_price`, `price.native_cod`; **няма tracking_link** → строим линк към куриера от `courier_awb` |
