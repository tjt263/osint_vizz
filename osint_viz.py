#!/usr/bin/env python3

import os
import sys
import argparse
import networkx as nx
from pyvis.network import Network
import csv
import json


class GraphToggleViz:
    def __init__(self, csv_file, output_file=None):
        self.csv_file = csv_file
        if output_file:
            self.output_file = output_file
        else:
            base = os.path.splitext(self.csv_file)[0]
            self.output_file = base + ".html"

        self.edges = []
        self.level_map = {}
        self.G = nx.Graph()
        self.net = Network(notebook=False, cdn_resources='in_line')

        self.type_config = {
            "domain": {"color": "#ADD8E6", "level": 1},
            "ns": {"color": "#90EE90", "level": 2},
            "mx": {"color": "#FFD580", "level": 3},
            "a": {"color": "#FF9999", "level": 4},
            "txt": {"color": "#D8BFD8", "level": 5},
            "cname": {"color": "#FFFACD", "level": 6},
        }

    def read_csv(self):
        with open(self.csv_file, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                domain = row['domain'].strip()
                rtype = row['record_type'].strip().lower()
                target = row['target'].strip()

                mx_priority = None
                txt_value = None

                if rtype == "mx" and " " in target:
                    parts = target.split(maxsplit=1)
                    mx_priority = parts[0].strip()
                    target = parts[1].strip().lower()

                elif rtype == "txt":
                    target_unquoted = target.strip().strip('"').strip()

                    if target_unquoted.lower().startswith("v=spf1"):
                        includes = []
                        parts = target_unquoted.split()
                        for part in parts:
                            if part.startswith("include:"):
                                includes.append(part.split("include:", 1)[1].strip())
                        if includes:
                            for spf_host in includes:
                                self.edges.append((domain, spf_host, rtype, None, target_unquoted))
                        else:
                            self.edges.append((domain, "SPF", rtype, None, target_unquoted))
                        continue

                    elif "v=dmarc1" in target_unquoted.lower():
                        target = "_dmarc." + domain
                        txt_value = target_unquoted

                    elif "v=dkim1" in target_unquoted.lower() or "_domainkey" in domain.lower():
                        target = domain
                        txt_value = target_unquoted

                    elif "=" in target_unquoted:
                        parts = target_unquoted.split("=", 1)
                        target = parts[0].strip().strip('"')
                        txt_value = parts[1].strip().strip('"')

                    elif target_unquoted.lower().startswith("zoom_verify_"):
                        parts = target_unquoted.split("_", 2)
                        if len(parts) == 3:
                            target = f"{parts[0]}_{parts[1]}"
                            txt_value = parts[2].strip().strip('"')

                if not self.is_ip(target):
                    target = target.rstrip('.')

                self.edges.append((domain, target, rtype, mx_priority, txt_value))

    def is_ip(self, s):
        parts = s.split(".")
        if len(parts) == 4:
            try:
                return all(0 <= int(p) <= 255 for p in parts)
            except:
                return False
        return False

    def build_graph(self):
        for domain, target, rtype, mx_priority, txt_value in self.edges:
            self.G.add_node(domain, type="domain")
            if target not in self.G:
                if self.is_ip(target):
                    self.G.add_node(target, type="a")
                else:
                    self.G.add_node(target, type=rtype)
            else:
                if not self.is_ip(target):
                    old_type = self.G.nodes[target]['type']
                    if old_type == "a" and rtype == "cname":
                        self.G.nodes[target]['type'] = "cname"
            self.G.add_edge(domain, target, type=rtype, priority=mx_priority, txt_value=txt_value)

    def build_pyvis(self):
        self.net.from_nx(self.G)

        for node in self.net.nodes:
            ntype = self.G.nodes[node["id"]].get("type", "unknown")
            config = self.type_config.get(ntype)
            if config:
                node["group"] = ntype
                node["color"] = config["color"]
                self.level_map[node["id"]] = config["level"]

                if ntype == "domain":
                    node["mass"] = 3
            else:
                node["group"] = "unknown"
                node["color"] = "#999"
                self.level_map[node["id"]] = 7

            node["borderWidth"] = 1.5
            node["size"] = 25
            node["font"] = {"strokeWidth": 2}

        for edge in self.net.edges:
            rtype = self.G.edges[edge["from"], edge["to"]].get("type", "unknown")
            edge["color"] = self.type_config.get(rtype, {}).get("color", "#999")
            edge["width"] = 1.5

            priority = self.G.edges[edge["from"], edge["to"]].get("priority")
            txt_value = self.G.edges[edge["from"], edge["to"]].get("txt_value")

            titles = []
            if priority:
                titles.append(priority)
            if txt_value:
                titles.append(txt_value)

            if titles:
                edge["title"] = "<br>".join(titles)

        self.net.options = {
            "nodes": {"borderWidth": 1.5},
            "groups": {
                k: {"color": v["color"]} for k, v in self.type_config.items()
            },
            "physics": {
                "enabled": True,
                "solver": "repulsion",
                "repulsion": {
                    "nodeDistance": 200,
                    "centralGravity": 0.1,
                    "springLength": 200,
                    "springConstant": 0.04
                },
                "hierarchicalRepulsion": {"nodeDistance": 0},
                "minVelocity": 0.75
            }
        }

    def export_html(self):
        self.net.write_html(self.output_file)
        with open(self.output_file) as f:
            html = f.read()

        legend_html = '<div id="legend" style="position:absolute; top:20px; left:20px; background:#fff; border:1px solid #ccc; padding:10px; z-index:999; color:#333;">'
        for k, v in self.type_config.items():
            legend_html += (
                f'<div style="margin:4px;">'
                f'<span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:{v["color"]}; margin-right:6px;"></span>'
                f'<span>{k.upper()}</span>'
                f'</div>'
            )
        legend_html += '</div>'

        custom_controls = f"""
<div style="position: relative; margin-bottom:5px; width: 100%;">
  <div style="display: flex; flex-wrap: wrap; gap: 5px; align-items: center;">
    <input id="searchBox" type="text" placeholder="Search..." oninput="updateSearch()" style="padding:5px; font-size:14px; width: 180px;">
    <button onclick="searchNode()">Search</button>
    <button onclick="toggleLayout()">Layout</button>
    <button onclick="toggleDarkMode()">Dark</button>
    <button onclick="toggleLegend()">Legend</button>
    <button onclick="decreaseRepulsion()">- Repulsion</button>
    <button onclick="increaseRepulsion()">+ Repulsion</button>
    <button onclick="decreaseNodeSize()">- Size</button>
    <button onclick="increaseNodeSize()">+ Size</button>
    <button onclick="decreaseFontSize()">- Text</button>
    <button onclick="increaseFontSize()">+ Text</button>
  </div>
  <div id="searchResults" style="position: absolute; top: 40px; left: 0; right: 0; background: #fff; border: 1px solid #ccc; max-height: 200px; overflow-y: auto; font-family: sans-serif; z-index: 9999;"></div>
</div>
<script>
  var hierarchicalEnabled = false;
  var repulsionDistance = 200;
  var nodeSize = 25;
  var fontSize = null;
  var isDarkMode = false;
  var myLevels = {json.dumps(self.level_map)};
  var myColors = {json.dumps({k: v["color"] for k, v in self.type_config.items()})};
  var searchResults = [];
  var searchIndex = 0;

  function applyAllUpdates() {{
    var updates = [];
    network.body.data.nodes.forEach(function(node) {{
      var ntype = node.group || 'unknown';
      var update = {{
        id: node.id,
        size: nodeSize,
        color: myColors[ntype] || "#999",
        font: {{
          size: fontSize || undefined,
          strokeWidth: 2,
          strokeColor: isDarkMode ? "#000" : "#fff",
          color: isDarkMode ? "#eee" : "#000"
        }}
      }};
      if (myLevels[node.id]) {{
        update.level = hierarchicalEnabled ? myLevels[node.id] : null;
      }}
      updates.push(update);
    }});
    network.body.data.nodes.update(updates);
  }}

  function increaseNodeSize() {{ nodeSize += 5; applyAllUpdates(); }}
  function decreaseNodeSize() {{ nodeSize = Math.max(5, nodeSize - 5); applyAllUpdates(); }}

  function increaseFontSize() {{
    if (fontSize === null) fontSize = 14;
    fontSize += 2;
    applyAllUpdates();
  }}

  function decreaseFontSize() {{
    if (fontSize === null) fontSize = 14;
    fontSize = Math.max(6, fontSize - 2);
    applyAllUpdates();
  }}

  function toggleDarkMode() {{
    isDarkMode = !isDarkMode;
    var body = document.body;
    var legend = document.getElementById('legend');
    var mynetwork = document.getElementById('mynetwork');
    if (isDarkMode) {{
      body.classList.add("dark-mode");
      legend.style.background = "#000"; legend.style.color = "#eee"; mynetwork.style.background = "#000";
      document.querySelectorAll('button').forEach(btn => {{ btn.style.background = "#333"; btn.style.color = "#eee"; btn.style.borderColor = "#666"; }});
    }} else {{
      body.classList.remove("dark-mode");
      legend.style.background = "#fff"; legend.style.color = "#333"; mynetwork.style.background = "#fff";
      document.querySelectorAll('button').forEach(btn => {{ btn.style.background = "#eee"; btn.style.color = "#000"; btn.style.borderColor = "#ccc"; }});
    }}
    applyAllUpdates();
  }}

  function toggleLayout() {{
    hierarchicalEnabled = !hierarchicalEnabled;
    if (hierarchicalEnabled) {{
      network.setOptions({{
        layout: {{ hierarchical: {{ enabled: true, levelSeparation: repulsionDistance, nodeSpacing: 400, treeSpacing: 300, direction: "UD", sortMethod: "hubsize" }} }},
        physics: {{ enabled: true, solver: "hierarchicalRepulsion", hierarchicalRepulsion: {{ nodeDistance: repulsionDistance }}, repulsion: {{ nodeDistance: 0 }} }}
      }});
    }} else {{
      network.setOptions({{
        layout: {{ hierarchical: {{ enabled: false }} }},
        physics: {{ enabled: true, solver: "repulsion",
          repulsion: {{ nodeDistance: repulsionDistance, centralGravity: 0.1, springLength: 200, springConstant: 0.04 }},
          hierarchicalRepulsion: {{ nodeDistance: 0 }} }}
      }});
    }}
    applyAllUpdates();
  }}

  function increaseRepulsion() {{ repulsionDistance += 50; updateRepulsion(); }}
  function decreaseRepulsion() {{ repulsionDistance = Math.max(50, repulsionDistance - 50); updateRepulsion(); }}
  function updateRepulsion() {{
    if (hierarchicalEnabled) {{
      network.setOptions({{ layout: {{ hierarchical: {{ levelSeparation: repulsionDistance }} }}, physics: {{ enabled: true, solver: "hierarchicalRepulsion", hierarchicalRepulsion: {{ nodeDistance: repulsionDistance }}, repulsion: {{ nodeDistance: 0 }} }} }});
    }} else {{
      network.setOptions({{ physics: {{ enabled: true, solver: "repulsion", repulsion: {{ nodeDistance: repulsionDistance, centralGravity: 0.1, springLength: 200, springConstant: 0.04 }}, hierarchicalRepulsion: {{ nodeDistance: 0 }} }} }});
    }}
  }}

  function toggleLegend() {{
    var legend = document.getElementById('legend');
    legend.style.display = (legend.style.display === "none") ? "block" : "none";
  }}

  function updateSearch() {{
    var query = document.getElementById('searchBox').value.trim().toLowerCase();
    searchResults = []; searchIndex = 0;
    if (query === "") {{ renderSearchResults(); return; }}
    network.body.data.nodes.forEach(function(node) {{
      if (node.id.toLowerCase().includes(query)) {{ searchResults.push(node.id); }}
    }});
    renderSearchResults();
  }}

  function searchNode() {{
    if (searchResults.length === 0) {{ alert("No match found."); return; }}
    var nodeId = searchResults[searchIndex];
    network.focus(nodeId, {{ scale: 1.5 }});
    searchIndex = (searchIndex + 1) % searchResults.length;
  }}

  function renderSearchResults() {{
    var container = document.getElementById('searchResults'); container.innerHTML = "";
    if (searchResults.length === 0) {{ container.innerHTML = "<div style='padding:4px; color:#888;'>No matches</div>"; return; }}
    searchResults.forEach(function(nodeId) {{
      var item = document.createElement('div'); item.textContent = nodeId;
      item.style = "padding:4px 8px; cursor:pointer; background:#fff; color:#000;";
      item.onmouseover = function() {{ item.style.background = '#eee'; }};
      item.onmouseout = function() {{ item.style.background = '#fff'; }};
      item.onclick = function() {{ network.focus(nodeId, {{ scale: 1.5 }}); }};
      container.appendChild(item);
    }});
  }}

  document.addEventListener('click', function(event) {{
    if (!event.target.closest('#searchBox') && !event.target.closest('#searchResults')) {{
      document.getElementById('searchResults').innerHTML = "";
    }}
  }});
</script>
"""
        html = html.replace(
            '<div id="mynetwork"',
            custom_controls + '<div style="position: relative;">' + legend_html + '\n<div id="mynetwork" style="position: relative; background: #fff;"'
        )

        with open(self.output_file, "w") as f:
            f.write(html)

    def run(self):
        self.read_csv()
        self.build_graph()
        self.build_pyvis()
        self.export_html()
        print(f"✅ Generated: {self.output_file}")


def main():
    parser = argparse.ArgumentParser(description="Visualize DNS CSVs as interactive HTML graphs.")
    parser.add_argument("input", help="Input CSV file or directory")
    args = parser.parse_args()

    if os.path.isfile(args.input):
        GraphToggleViz(args.input).run()
    elif os.path.isdir(args.input):
        for f in os.listdir(args.input):
            if f.lower().endswith(".csv"):
                GraphToggleViz(os.path.join(args.input, f)).run()
    else:
        print(f"❌ Invalid input: {args.input}")
        sys.exit(1)


if __name__ == "__main__":
    main()