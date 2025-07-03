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
        "domain": {"color": "#ADD8E6", "level": 1},   # Light Blue (Domain)
        "mx": {"color": "#FFD580", "level": 2},       # Light Orange (MX)
        "ns": {"color": "#90EE90", "level": 2},       # Light Green (NS)
        "a": {"color": "#FF9999", "level": 3},        # Light Red/Pink (A Record)
        "txt": {"color": "#D8BFD8", "level": 3},      # Light Purple (TXT)
        "cname": {"color": "#FFFACD", "level": 3},    # Lemon Chiffon (CNAME)
        }

    def read_csv(self):
        with open(self.csv_file, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                domain = row['domain']
                rtype = row['record_type'].strip().lower()
                target = row['target']
                self.edges.append((domain, target, rtype))

    def build_graph(self):
        for domain, target, rtype in self.edges:
            self.G.add_node(domain, type="domain")
            self.G.add_node(target, type=rtype)
            self.G.add_edge(domain, target)

    def build_pyvis(self):
        self.net.from_nx(self.G)

        for node in self.net.nodes:
            ntype = self.G.nodes[node["id"]].get("type", "unknown")
            config = self.type_config.get(ntype)

            if config:
                node["color"] = config["color"]
                if not self.G.nodes[node["id"]].get("is_legend"):
                    self.level_map[node["id"]] = config["level"]
            else:
                node["color"] = "#D3D3D3"

            node["group"] = ntype
            node["borderWidth"] = 1.5

        for edge in self.net.edges:
            edge["width"] = 1.5

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
<div style="margin-bottom:5px;">
  <button onclick="toggleLayout()" style="
    display:inline-block;
    width:auto;
    padding:5px 10px;
    font-size:14px;
    border:1px solid #ccc;
    background:#eee;
    cursor:pointer;
  ">Toggle Layout</button>
</div>
<script>
  var hierarchicalEnabled = false;
  var myLevels = {json.dumps(self.level_map)};

  function toggleLayout() {{
    hierarchicalEnabled = !hierarchicalEnabled;

    var options = {{
      layout: {{
        hierarchical: {{
          enabled: hierarchicalEnabled,
          levelSeparation: 150,
          nodeSpacing: 200,
          treeSpacing: 200,
          direction: "UD",
          sortMethod: "hubsize"
        }}
      }},
      physics: {{
        hierarchicalRepulsion: {{
          nodeDistance: 150
        }},
        minVelocity: 0.75
      }}
    }};
    network.setOptions(options);

    var updates = [];
    network.body.data.nodes.forEach(function(node) {{
      if (myLevels[node.id]) {{
        if (hierarchicalEnabled) {{
          updates.push(Object.assign({{}}, node, {{ level: myLevels[node.id] }}));
        }} else {{
          updates.push(Object.assign({{}}, node, {{ level: null }}));
        }}
      }}
    }});
    network.body.data.nodes.update(updates);
  }}
</script>
"""

        html = html.replace(
            '<div id="mynetwork"',
            custom_controls +
            '<div style="position: relative;">'
            + legend_html +
            '\n<div id="mynetwork" style="position: relative;"'
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
    parser = argparse.ArgumentParser(description="GraphToggleViz CLI — Process single CSV or a directory of CSVs.")
    parser.add_argument("path", help="Path to CSV file or directory containing CSV files")
    args = parser.parse_args()

    if os.path.isfile(args.path):
        viz = GraphToggleViz(args.path)
        viz.run()
    elif os.path.isdir(args.path):
        for filename in os.listdir(args.path):
            if filename.lower().endswith(".csv"):
                csv_path = os.path.join(args.path, filename)
                viz = GraphToggleViz(csv_path)
                viz.run()
    else:
        print(f"❌ Error: Path '{args.path}' is not a valid file or directory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
