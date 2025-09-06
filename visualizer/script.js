// D3.js script to visualize the family tree

document.addEventListener('DOMContentLoaded', () => {
    console.log('[DEBUG] DOMContentLoaded event fired.');

    const container = document.getElementById('visualization-container');
    console.log('[DEBUG] Container element:', container);

    if (!container) {
        console.error('Visualization container not found');
        return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;
    console.log(`[DEBUG] Container dimensions: width=${width}, height=${height}`);

    if (width === 0 || height === 0) {
        console.error('[DEBUG] Container has zero width or height. The visualization will not be visible.');
    }

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g');
    console.log('[DEBUG] SVG and G elements created.');

    svg.call(d3.zoom().on("zoom", (event) => {
        g.attr('transform', event.transform);
    }));

    const nodeSize = 32;

    // Define a clip path for circular images, this is referenced later
    g.append('defs').append('clipPath')
        .attr('id', 'clip-circle')
        .append('circle')
        .attr('r', nodeSize / 2);

    d3.json('data.json').then(data => {
        console.log('[DEBUG] data.json loaded successfully:', data);

        const links = data.edges.map(d => ({ source: d.from, target: d.to, type: d.type }));
        const nodes = data.nodes;
        console.log('[DEBUG] Nodes and links mapped for simulation.');

        // --- HIERARCHY CALCULATION START ---
        function calculateGenerations(nodes, links) {
            const nodeMap = new Map(nodes.map(node => [node.id, node]));

            // Initial setup: find roots (those who are not children) and set their generation to 0.
            const childIds = new Set(links.filter(l => l.type === 'child').map(l => l.to));
            nodes.forEach(node => {
                node.generation = !childIds.has(node.id) ? 0 : -1;
            });

            // Iteratively propagate generations until no more changes are made
            let changedInPass = true;
            while (changedInPass) {
                changedInPass = false;

                // Propagate generations to children
                links.filter(l => l.type === 'child').forEach(link => {
                    const parent = nodeMap.get(link.from);
                    const child = nodeMap.get(link.to);
                    if (parent && child && parent.generation !== -1) {
                        const newGen = parent.generation + 1;
                        if (child.generation === -1 || newGen > child.generation) {
                            child.generation = newGen;
                            changedInPass = true;
                        }
                    }
                });

                // Propagate generations to partners
                links.filter(l => l.type === 'partner').forEach(link => {
                    const p1 = nodeMap.get(link.from);
                    const p2 = nodeMap.get(link.to);
                    if (p1 && p2) {
                        if (p1.generation !== -1 && p2.generation !== p1.generation) {
                            p2.generation = p1.generation;
                            changedInPass = true;
                        } else if (p2.generation !== -1 && p1.generation !== p2.generation) {
                            p1.generation = p2.generation;
                            changedInPass = true;
                        }
                    }
                });
            }

            let maxGeneration = 0;
            nodes.forEach(node => {
                if (node.generation > maxGeneration) {
                    maxGeneration = node.generation;
                }
            });
            return maxGeneration;
        }

        const maxGeneration = calculateGenerations(nodes, data.edges); // Use original edges for calculation
        console.log('[DEBUG] Hierarchy calculated. Max generation:', maxGeneration);
        console.log("[DEBUG] Calculated Generations:", nodes.map(n => ({ name: n.name, gen: n.generation })));

        const levelHeight = 180; // More vertical spacing

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).strength(0.4).distance(100))
            .force("charge", d3.forceManyBody().strength(-600)) // Increased repulsion
            .force("collide", d3.forceCollide(nodeSize + 10)) // Increased collision radius
            .force("x", d3.forceX(width / 2).strength(0.02))
            .force("y", d3.forceY(d => height - 100 - (d.generation * levelHeight)).strength(d => d.generation === -1 ? 0 : 1));

        console.log('[DEBUG] Force simulation created with hierarchical forces.');

        const link = g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(links)
            .enter().append("line")
            .attr("class", d => `link ${d.type}`);

        const node = g.append("g")
            .attr("class", "nodes")
            .selectAll("g")
            .data(nodes)
            .enter().append("g")
            .attr("class", "node")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        // Append either an image or a fallback circle
        node.each(function(d) {
            const group = d3.select(this);
            if (d.photo_path) {
                group.append("image")
                    .attr("xlink:href", d.photo_path)
                    .attr("clip-path", "url(#clip-circle)")
                    .attr("x", -nodeSize / 2)
                    .attr("y", -nodeSize / 2)
                    .attr("width", nodeSize)
                    .attr("height", nodeSize);
            } else {
                group.append("circle")
                    .attr("r", nodeSize / 2)
                    .attr("fill", "#ccc")
                    .attr("stroke", "#fff")
                    .attr("stroke-width", "1.5px");
            }
        });

        // Append text labels, positioned below the node
        node.append("text")
            .text(d => d.name)
            .attr("y", (nodeSize / 2) + 14) // Adjust vertical position
            .attr("class", "label");

        console.log('[DEBUG] SVG nodes and links created.');

        let tickCount = 0;
        simulation.on("tick", () => {
            if (tickCount < 5) { // Log first 5 ticks
                console.log(`[DEBUG] Simulation tick ${tickCount + 1}`);
                tickCount++;
            }
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => `translate(${d.x},${d.y})`);
        });

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }

        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }

        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }

    }).catch(error => {
        console.error('[DEBUG] Critical error loading or processing data.json:', error);
    });
});
