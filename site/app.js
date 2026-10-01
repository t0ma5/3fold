(function () {
  var app = document.getElementById("app");
  var banner = document.getElementById("banner");
  var pause = document.getElementById("pause");

  var STELLAR_ACCOUNT = /G[A-Z2-7]{55}/g;

  function stellarLink(account) {
    var a = document.createElement("a");
    a.className = "addr-link";
    a.href = "https://stellar.expert/explorer/public/account/" + account;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = account;
    return a;
  }

  function appendLinked(parent, text) {
    var s = text == null ? "" : String(text);
    var re = new RegExp(STELLAR_ACCOUNT.source, "g");
    var last = 0;
    var match;
    while ((match = re.exec(s))) {
      if (match.index > last) parent.appendChild(document.createTextNode(s.slice(last, match.index)));
      parent.appendChild(stellarLink(match[0]));
      last = match.index + match[0].length;
    }
    if (last < s.length) parent.appendChild(document.createTextNode(s.slice(last)));
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) appendLinked(node, text);
    return node;
  }

  function fail(message) {
    app.textContent = "";
    var p = el("p", "status error", message);
    p.setAttribute("role", "alert");
    app.appendChild(p);
  }

  function emptyNote(text) {
    return el("p", "empty", text);
  }

  function addressNode(value) {
    if (!value) return null;
    if (/^G[A-Z2-7]{55}$/.test(value)) {
      var link = stellarLink(value);
      link.className = "addr";
      return link;
    }
    var code = el("code", "addr", value);
    return code;
  }

  function supplySection(supply) {
    var section = el("section");
    section.id = "supply";
    section.appendChild(el("p", "kicker", supply.kicker || "Unique supply"));
    section.appendChild(el("h1", null, supply.headline || "Each TFT once."));
    if (supply.lede) section.appendChild(el("p", "lede", supply.lede));

    var total = supply.total || {};
    var box = el("div", "total");
    var figure = el("p", "total-tft");
    figure.id = "unique-supply-total";
    figure.textContent = (total.tft || "—") + " TFT";
    box.appendChild(figure);

    var facts = el("ul", "facts");
    [
      [total.sporeIfSwapped, "SPORE if swapped 1:10"],
      [total.usdLabeled ? "$" + total.usdLabeled : "—", "SPORE at $0.01"]
    ].forEach(function (pair) {
      var li = el("li");
      li.appendChild(el("b", null, pair[0] || "—"));
      li.appendChild(el("span", null, pair[1]));
      facts.appendChild(li);
    });
    box.appendChild(facts);
    if (total.roundingNote) box.appendChild(el("p", "fine", total.roundingNote));
    if (total.cashNote) box.appendChild(el("p", "fine", total.cashNote));
    section.appendChild(box);

    var rows = Array.isArray(supply.rows) ? supply.rows : [];
    if (!rows.length) {
      section.appendChild(emptyNote("This snapshot has no unique-supply rows."));
    } else {
      var list = el("div", "rows");
      rows.forEach(function (row) {
        var card = el("article", "row");
        var copy = el("div");
        copy.appendChild(el("h2", "place", row.place || "Untitled slice"));
        if (row.detail) copy.appendChild(el("p", "detail", row.detail));
        var addr = addressNode(row.address);
        if (addr) copy.appendChild(addr);
        card.appendChild(copy);

        var tft = el("p", "metric");
        tft.appendChild(el("b", null, (row.tft || "—") + " TFT"));
        tft.appendChild(el("span", null, "Amount"));
        card.appendChild(tft);
        list.appendChild(card);
      });
      section.appendChild(list);
    }
    return section;
  }

  function accountCell(account, explorer) {
    var td = el("td", "acct");
    if (!account) {
      td.textContent = "—";
      return td;
    }
    if (explorer && /^0x[a-fA-F0-9]{40}$/.test(account)) {
      var a = document.createElement("a");
      a.className = "addr-link";
      a.href = explorer + account;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = account;
      td.appendChild(a);
      return td;
    }
    appendLinked(td, account);
    return td;
  }

  function walletSection(note) {
    var section = el("section");
    section.id = "wallet";
    section.appendChild(el("h2", null, (note && note.title) || "Top 2 Stellar Wallet"));
    if (note && note.intro) section.appendChild(el("p", "lede", note.intro));
    var points = note && Array.isArray(note.points) ? note.points : [];
    if (points.length) {
      var list = el("ol", "points");
      points.forEach(function (point) {
        list.appendChild(el("li", null, point));
      });
      section.appendChild(list);
    }
    if (note && note.close) section.appendChild(el("p", "aside", note.close));
    return section;
  }

  function holderTable(id, block) {
    var section = el("section");
    section.id = id;
    section.appendChild(el("h2", null, block.title || "Holders"));
    if (block.lede) section.appendChild(el("p", "lede", block.lede));
    var rows = Array.isArray(block.rows) ? block.rows : [];
    if (!rows.length) {
      section.appendChild(emptyNote("This snapshot has no rows in this section."));
      return section;
    }
    var wrap = el("div", "table-wrap");
    var table = el("table");
    var caption = el("caption", null, "Swipe sideways on a small screen to read the full address.");
    table.appendChild(caption);
    var thead = el("thead");
    var hr = el("tr");
    ["#", "Name", "TFT", "Share", "Account"].forEach(function (label, index) {
      var th = el("th", index === 2 || index === 3 ? "num" : null, label);
      th.scope = "col";
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = el("tbody");
    rows.forEach(function (row) {
      var tr = el("tr");
      tr.appendChild(el("td", "num", String(row.rank != null ? row.rank : "")));
      var nameCell = el("td");
      var unmatched = row.name === "No public match";
      nameCell.appendChild(el("div", unmatched ? "who unmatched" : "who", row.name || "No public match"));
      if (row.note) nameCell.appendChild(el("p", "who-note", row.note));
      tr.appendChild(nameCell);
      tr.appendChild(el("td", "num", row.tft || "—"));
      tr.appendChild(el("td", "num", row.share || "—"));
      tr.appendChild(accountCell(row.account, block.explorer));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    section.appendChild(wrap);
    return section;
  }

  function portalSection(portal) {
    var section = el("section");
    section.id = "portal";
    section.appendChild(el("h2", null, portal.title || "Portal note"));
    if (portal.summary) section.appendChild(el("p", "lede", portal.summary));
    var quotes = Array.isArray(portal.quotes) ? portal.quotes : [];
    if (!quotes.length) {
      section.appendChild(emptyNote("This snapshot has no portal quotations."));
    } else {
      var list = el("ul", "quotes");
      quotes.forEach(function (quote) {
        list.appendChild(el("li", null, quote));
      });
      section.appendChild(list);
    }
    if (portal.source) section.appendChild(el("p", "note", portal.source));
    if (portal.aside) section.appendChild(el("p", "aside", portal.aside));
    return section;
  }

  function methodSection(method) {
    var section = el("section");
    section.id = "method";
    section.appendChild(el("h2", null, method.title || "How the numbers were read"));
    var rows = Array.isArray(method.rows) ? method.rows : [];
    if (!rows.length) {
      section.appendChild(emptyNote("This snapshot has no source notes."));
      return section;
    }
    var list = el("div", "method");
    rows.forEach(function (row) {
      var article = el("article");
      article.appendChild(el("h3", null, row.title || "Source"));
      article.appendChild(el("p", null, row.body || ""));
      list.appendChild(article);
    });
    section.appendChild(list);
    return section;
  }

  fetch("snapshot.json", { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || typeof data !== "object") throw new Error("Snapshot was not an object.");
      if (data.snapshotLabel) {
        banner.textContent = "Snapshot " + data.snapshotLabel;
        if (data.snapshotDetail) banner.title = data.snapshotDetail;
      }
      if (data.pauseNote) pause.textContent = data.pauseNote;
      app.textContent = "";
      app.appendChild(supplySection(data.supply || {}));
      app.appendChild(holderTable("stellar", data.stellar || {}));
      app.appendChild(holderTable("tfchain", data.tfchain || {}));
      app.appendChild(holderTable("bsc", data.bsc || {}));
      app.appendChild(portalSection(data.portal || {}));
      app.appendChild(walletSection(data.topStellarWallet || {}));
      app.appendChild(methodSection(data.method || {}));
    })
    .catch(function () {
      fail("snapshot.json did not load. This page keeps no second copy of the figures.");
    });
})();
