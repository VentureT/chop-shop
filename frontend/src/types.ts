export type Body = 'Coupe' | 'Convertible' | 'Sedan' | 'Hatchback' | 'Wagon' | 'SUV' | 'Pickup' | 'Van' | 'Unknown';

export interface VehicleProfile {
  vin: string;
  year: number;
  make: string;
  model: string;
  trim: string;
  series: string;
  body: Body;
  doors: number | null;
  drive: string;
  engine_cyl: number | null;
  displacement_l: number | null;
  fuel: string;
  transmission: string;
  turbo: boolean;
  plant_country: string;
  decode_warnings: string[];
}

export interface Options {
  headlights: 'halogen' | 'xenon' | 'led';
  wheel_size: 16 | 17 | 18 | 19 | 20 | 21;
  audio: 'standard' | 'premium';
  navigation: boolean;
  seats: 'standard' | 'sport';
  sunroof: boolean;
  sport_package: boolean;
  convertible_top: boolean;
}

export const DEFAULT_OPTIONS: Options = {
  headlights: 'xenon',
  wheel_size: 18,
  audio: 'standard',
  navigation: true,
  seats: 'standard',
  sunroof: true,
  sport_package: false,
  convertible_top: false,
};

export interface Flag {
  code: string;
  severity: 'info' | 'warn' | 'block';
  title: string;
  detail: string;
  source: string;
}

export interface PartType {
  id: string;
  hollander: string;
  name: string;
  group: string;
  qty: number;
  ebay_q: string;
  size_class: 'S' | 'M' | 'L' | 'XL';
  removal_hours: number;
  reference_asking: number;
  flags: string[];
}

export interface Listing {
  item_id: string;
  title: string;
  price: number;
  condition: string;
  compatibility_match: string;
  url: string;
  shipping: number | null;
}

export type PriceStatus = 'live' | 'cached' | 'reference' | 'no_results' | 'error' | 'no_credentials';

export interface PartValuation {
  part: PartType;
  query: string;
  price_status: PriceStatus;
  sample_size: number;
  exact_share: number;
  asking_median: number;
  asking_low: number;
  asking_high: number;
  est_sold_each: number;
  est_net_each: number;
  est_net_total: number;
  sellable: boolean;
  confidence: 'none' | 'low' | 'medium' | 'high';
  confidence_reason: string;
  flags: Flag[];
  sample_listings: Listing[];
  note: string;
}

export interface Totals {
  parts_considered: number;
  parts_sellable: number;
  gross_asking: number;
  est_sold: number;
  est_net: number;
  removal_hours: number;
  top_10_removal_hours: number;
  live_priced: number;
  top_10_share: number;
}

export interface ValuateResponse {
  vehicle: VehicleProfile;
  options: Options;
  parts: PartValuation[];
  totals: Totals;
  vehicle_flags: Flag[];
  ebay_live: boolean;
}

export interface CompareResponse {
  instant_offer: number;
  private_party: number;
  part_out_gross_asking: number;
  part_out_est_sold: number;
  part_out_est_net: number;
  part_out_net_after_labor: number;
  total_hours: number;
  months_estimate: string;
  sell_through: number;
  shell_scrap: number;
  winner: 'instant_offer' | 'private_party' | 'part_out';
  notes: string[];
}

export interface Status {
  ebay_configured: boolean;
  ebay_env: string;
  state: string;
}

export interface ValuationJob {
  job_id: string;
  status: 'running' | 'done' | 'error';
  done: number;
  total: number;
  result: ValuateResponse | null;
  error: string;
}
