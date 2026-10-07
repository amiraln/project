// Закладки для e-orda: собирают данные на странице e-orda и передают их в окно сайта /payments/eorda/.
// Файл встроен в страницу табеля (index.html), поэтому перетащенная оттуда закладка всегда с актуальным кодом.
// Функция eordaBookmarklet целиком превращается в закладку, поэтому ей нельзя обращаться к чему-то снаружи.

async function eordaBookmarklet(site, kind) {
  var win = window.open(site, "botakanym");
  if (!win) return alert("Разрешите всплывающие окна для этого сайта");
  // Окно сайта сообщает, что готово, и присылает детей и группы из табеля
  var bridge = await new Promise(function (resolve) {
    window.addEventListener("message", function (e) {
      if (e.source === win && e.data && e.data.ready) resolve(e.data);
    });
  });
  function send(message) {
    win.postMessage(Object.assign({ v: 3 }, message), new URL(site).origin);
  }

  var NO_LOGIN = "Нет входа в e-orda";
  async function getJson(url, body) {
    var opts = { cache: "no-store", headers: { "X-Requested-With": "XMLHttpRequest" } };
    if (body) {
      opts.method = "POST";
      opts.body = body;
      opts.headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8";
    }
    var r = await fetch(url, opts);
    if (!r.ok) throw new Error("e-orda ответила ошибкой " + r.status);
    if (!(r.headers.get("content-type") || "").includes("json")) throw new Error(NO_LOGIN);
    return r.json();
  }
  async function get(url, body) {
    return (await getJson(url, body)).result;
  }
  // Номера, которые e-orda уже запрашивала на этой странице (адрес страницы всегда /ru, в нём их нет)
  function seen(re) {
    return performance.getEntriesByType("resource").map(function (e) {
      var m = e.name.match(re);
      return m && m[1];
    }).filter(Boolean);
  }

  try {
    if (kind === "timesheet") {
      var id = seen(/GetTimesheetBlank\?(?:.*&)?id=(\d+)/).pop();
      if (!id) throw new Error("Откройте табель в e-orda");
      var base = "/ru/Timesheet/GetTimesheetBlank?id=" + id + "&page=1&start=0&limit=2000";
      var rows = {};
      for (var g of [0, 2, 3, 4, 5, 6]) {
        var filter = g ? "&filter=" + encodeURIComponent(JSON.stringify([{ property: "gId", value: g, operator: "eq" }])) : "";
        ((await get(base + filter)) || []).forEach(function (r) {
          rows[r.pId] = r;
        });
      }
      send({ kind: kind, id: id, rows: Object.values(rows) });
    } else {
      // Контакты родителей и адрес — из карточки каждого ребёнка (GetPupil), договор — из списка его договоров.
      // Группы (KindergardenGroupId) берём из табеля сайта, из открытых на этой странице и из карточек детей;
      // детей — из списков этих групп и из табеля.
      var groups = (bridge.groups || []).concat(seen(/GetGroupPupilList\?(?:.*&)?id=(\d+)/).map(Number));
      var kids = [];
      var known = {};
      var addKid = function (childId) {
        if (!known[childId]) {
          known[childId] = true;
          kids.push(childId);
        }
      };
      (bridge.children || []).forEach(addKid);
      if (!groups.length && !kids.length) throw new Error("Сначала загрузите табель: по нему сайт знает, чьи контакты загружать");

      var listed = {};
      var pupils = [];
      var failed = 0;
      var failedGroups = [];
      var failedContracts = 0;
      // Договоры ребёнка: номер и дата подписания. null — список не открылся, тогда прежний договор на сайте остаётся
      var loadContracts = async function (childId) {
        try {
          var res = await getJson("/ru/Contract/GetContractGridForPupil?id=" + childId + "&page=1&start=0&limit=50");
          var list = [res.result, res.data, res.rows, res].find(Array.isArray);
          if (!list) throw new Error("Договоры в неожиданном формате");
          return list.map(function (c) {
            return { number: c.Number == null ? "" : String(c.Number), date: c.CreatedDate || "" };
          });
        } catch (e) {
          if (e.message === NO_LOGIN) throw e;
          failedContracts++;
          return null;
        }
      };
      var loadCard = async function (childId) {
        try {
          var both = await Promise.all([get("/ru/Pupil/GetPupil", "id=" + childId), loadContracts(childId)]);
          var card = both[0];
          if (!card || !card.Id) throw new Error("Карточка не открылась");
          if (card.KindergardenGroupId) groups.push(card.KindergardenGroupId);
          var pupil = {
            p_id: childId,
            iin: card.ChildrenIin || "",
            fio: [card.ChildLastName, card.ChildFirstName, card.ChildMiddleName].filter(Boolean).join(" "),
            guardians: (card.Guardians || []).map(function (p) {
              return {
                gender: p.Gender != null ? p.Gender : p.gender, // 1 — отец, 2 — мать
                iin: p.Iin || "",
                fio: [p.LastName, p.FirstName, p.MiddleName].filter(Boolean).join(" "),
                phone: [p.PhoneMain, p.PhoneAdd].filter(Boolean).join(", "),
                email: p.Email || "",
              };
            }),
          };
          var address = typeof card.ChildAddress === "string" ? card.ChildAddress.trim() : "";
          if (address) pupil.address = address; // нет адреса в карточке — прежний на сайте остаётся
          if (both[1]) pupil.contracts = both[1];
          pupils.push(pupil);
        } catch (e) {
          if (e.message === NO_LOGIN) throw e;
          failed++; // карточка не открылась — прежние контакты этого ребёнка на сайте не трогаем
        }
      };

      while (groups.length || kids.length) {
        if (groups.length) {
          var group = groups.shift();
          if (listed[group]) continue;
          listed[group] = true;
          try {
            ((await get("/ru/Group/GetGroupPupilList?id=" + group + "&page=1&start=0&limit=500")) || []).forEach(function (kid) {
              addKid(kid.Id);
            });
          } catch (e) {
            if (e.message === NO_LOGIN) throw e;
            failedGroups.push(group);
          }
          continue;
        }
        await Promise.all(kids.splice(0, 6).map(loadCard)); // по 6 карточек за раз
        send({ kind: "progress", done: pupils.length + failed, total: pupils.length + failed + kids.length });
      }
      if (!pupils.length) throw new Error("Не удалось открыть карточки детей в e-orda");
      send({ kind: kind, pupils: pupils, failed: failed, failedGroups: failedGroups, failedContracts: failedContracts });
    }
  } catch (e) {
    send({ error: e.message });
  }
}

function bookmarklet(site, kind) {
  return "javascript:" + encodeURIComponent("(" + eordaBookmarklet + ")(" + JSON.stringify(site) + "," + JSON.stringify(kind) + ");void 0");
}
