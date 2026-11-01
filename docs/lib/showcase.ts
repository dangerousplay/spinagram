// Every rendered diagram the docs show with its source. `files` are paths under examples/ and become the code
// tabs, in order. Assets come from docs/scripts/render_assets.sh.

export interface ShowcaseView {
  label: string;
  src: string;
  alt: string;
  files: string[];
}

export const views = {
  // one diagram, four stylesheets
  l01: { label: 'Midnight', src: '/assets/examples/l01.svg', alt: 'Dark canvas with neon outlines and a glowing Orders service', files: ['looks/_platform.py', 'looks/looks.py', 'looks/midnight.css'] },
  l02: { label: 'Blueprint', src: '/assets/examples/l02.svg', alt: 'White lines on drafting blue', files: ['looks/_platform.py', 'looks/looks.py', 'looks/blueprint.css'] },
  l03: { label: 'Pastel', src: '/assets/examples/l03.svg', alt: 'Soft tinted cards with gentle shadows', files: ['looks/_platform.py', 'looks/looks.py', 'looks/pastel.css'] },
  l04: { label: 'Editorial', src: '/assets/examples/l04.svg', alt: 'Black and white with a red critical service', files: ['looks/_platform.py', 'looks/looks.py', 'looks/editorial.css'] },

  // the tutorial, one step at a time
  t01: { label: '1 · Boxes', src: '/assets/tutorial/t01.svg', alt: 'The checkout as plain boxes and arrows', files: ['tutorial/step1_boxes.py'] },
  t02: { label: '2 · Details', src: '/assets/tutorial/t02.svg', alt: 'The checkout with icons and labels', files: ['tutorial/step2_details.py'] },
  t03: { label: '3 · Groups', src: '/assets/tutorial/t03.svg', alt: 'The checkout grouped into zones', files: ['tutorial/step3_groups.py'] },
  t04: { label: '4 · Explain', src: '/assets/tutorial/t04.svg', alt: 'The checkout with numbered steps, a callout and a legend', files: ['tutorial/step4_explain.py'] },
  t05: { label: '5 · Style', src: '/assets/tutorial/t05.svg', alt: 'The checkout styled with a stylesheet', files: ['tutorial/step5_style.py', 'tutorial/checkout.css'] },

  // several diagram types on one canvas
  m01: { label: 'Payments', src: '/assets/examples/m01.svg', alt: 'Architecture, a fraud-check flowchart and the payment state machine', files: ['mixed/payments.py', 'mixed/mixed.css'] },
  m02: { label: 'Incident', src: '/assets/examples/m02.svg', alt: 'The monitoring stack and an incident-response activity with lanes', files: ['mixed/incident.py', 'mixed/mixed.css'] },
  b04: { label: 'Orders lifecycle', src: '/assets/demo/b04.svg', alt: 'An architecture next to the state machine of one of its services', files: ['behavior/mixed.py'] },

  // behavior
  b01: { label: 'Flowchart', src: '/assets/demo/b01.svg', alt: 'Checkout flowchart with two decisions and a retry loop', files: ['behavior/flowchart.py'] },
  b02: { label: 'State machine', src: '/assets/demo/b02.svg', alt: 'Order lifecycle with a composite state and two parallel regions', files: ['behavior/state_machine.py'] },
  b03: { label: 'Swimlanes', src: '/assets/demo/b03.svg', alt: 'Order fulfilment across Customer, Shop and Warehouse lanes', files: ['behavior/activity.py'] },

  // Kubernetes
  eks01: { label: 'EKS platform', src: '/assets/examples/eks01.svg', alt: 'Kubernetes platform on Amazon EKS with Cilium, Gateway API, Karpenter and Argo CD', files: ['kubernetes/eks_platform.py', 'kubernetes/eks.css', 'showcase/showcase.css'] },
  eks02: { label: 'Gateway API', src: '/assets/examples/eks02.svg', alt: 'Gateway API routing with HTTPRoute rules as a flowchart', files: ['kubernetes/eks_gateway.py', 'kubernetes/eks.css', 'showcase/showcase.css'] },
  eks03: { label: 'GitOps', src: '/assets/examples/eks03.svg', alt: 'Shipping a change with GitOps in swimlanes', files: ['kubernetes/eks_gitops.py', 'kubernetes/gitops.css'] },
  k8s01: { label: 'Workload', src: '/assets/gallery/k8s01.svg', alt: 'Anatomy of a Kubernetes workload on a dark canvas', files: ['showcase/k8s_platform.py', 'showcase/k8s.css', 'showcase/showcase.css'] },
  k8s02: { label: 'Service networking', src: '/assets/gallery/k8s02.svg', alt: 'Ingress to Service to pods, guarded by NetworkPolicy', files: ['showcase/k8s_networking.py', 'showcase/k8s.css', 'showcase/showcase.css'] },

  // clouds
  aws01: { label: 'AWS three tiers', src: '/assets/gallery/aws01.svg', alt: 'Three-tier web application on AWS', files: ['showcase/aws_three_tier.py', 'showcase/aws.css', 'showcase/showcase.css'] },
  aws02: { label: 'AWS hub and spoke', src: '/assets/gallery/aws02.svg', alt: 'Hub-and-spoke networking on AWS', files: ['showcase/aws_network_hub.py', 'showcase/aws.css', 'showcase/showcase.css'] },
  gcp01: { label: 'Google Cloud', src: '/assets/gallery/gcp01.svg', alt: 'Global web application on Google Cloud', files: ['showcase/gcp_global_app.py', 'showcase/gcp.css', 'showcase/showcase.css'] },
  quickstart: { label: 'Quickstart', src: '/assets/quickstart.svg', alt: 'Web app on AWS, laid out automatically', files: ['quickstart.py'] },

  // icons
  i01: { label: 'Every pack', src: '/assets/examples/i01.svg', alt: 'Cards in six groups, each showing an icon and its pack:name reference', files: ['icons/hybrid.py', 'icons/icons.css'] },
  ai01: { label: 'AI delivery', src: '/assets/gallery/ai01.svg', alt: 'GitLab to Harbor and Argo CD, with an AI gateway in front of the models', files: ['showcase/delivery_ai.py', 'showcase/delivery_ai.css', 'showcase/showcase.css'] },

  // networks
  home01: { label: 'Homelab', src: '/assets/gallery/home01.svg', alt: 'Homelab private cloud on Proxmox behind OPNsense, split into VLANs', files: ['showcase/homelab.py', 'showcase/homelab.css', 'showcase/showcase.css'] },
  net01: { label: 'Campus', src: '/assets/gallery/net01.svg', alt: 'Campus network with a redundant core and access layer', files: ['showcase/campus_network.py', 'showcase/campus.css', 'showcase/showcase.css'] },
  net02: { label: 'EVPN fabric', src: '/assets/gallery/net02.svg', alt: 'EVPN-VXLAN data center fabric with an eBGP underlay', files: ['showcase/evpn_fabric.py', 'showcase/fabric.css', 'showcase/showcase.css'] },

  // slides
  note01: { label: 'Decisions', src: '/assets/gallery/note01.svg', alt: 'Architecture decisions slide with cards, a quote and open questions', files: ['showcase/notes.py', 'showcase/notes.css', 'showcase/showcase.css'] },
} satisfies Record<string, ShowcaseView>;

export type ViewId = keyof typeof views;
