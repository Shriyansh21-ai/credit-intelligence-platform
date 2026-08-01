import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";

const KEY = "financial-intelligence";

// M1 Treasury
export const useFundingSources = () => useQuery({ queryKey: [KEY, "funding"], queryFn: api.listFundingSources });
export const useTreasuryDashboard = () => useQuery({ queryKey: [KEY, "treasury-dash"], queryFn: api.treasuryDashboard });
export const useCreateFundingSource = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.createFundingSource,
    onSuccess: () => { qc.invalidateQueries({ queryKey: [KEY, "funding"] });
                       qc.invalidateQueries({ queryKey: [KEY, "treasury-dash"] }); } });
};
export const useLcr = () => useMutation({ mutationFn: api.lcr });
export const useNsfr = () => useMutation({ mutationFn: api.nsfr });
export const useCashForecast = () => useMutation({ mutationFn: api.cashForecast });

// M2 Portfolio
export const usePortfolios = () => useQuery({ queryKey: [KEY, "portfolios"], queryFn: api.listPortfolios });
export const useCreatePortfolio = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.createPortfolio,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "portfolios"] }) });
};
export const useSyncPortfolio = () => useMutation({ mutationFn: (id: number) => api.syncPortfolio(id) });
export const usePortfolioSummary = () => useMutation({ mutationFn: (id: number) => api.portfolioSummary(id) });
export const usePortfolioConcentration = () => useMutation({ mutationFn: (id: number) => api.portfolioConcentration(id) });
export const usePortfolioSimulate = () => useMutation({ mutationFn: (id: number) => api.portfolioSimulate(id) });
export const usePortfolioInsights = () => useMutation({ mutationFn: (id: number) => api.portfolioInsights(id) });

// M3 Regulatory
export const useRegDashboard = () => useQuery({ queryKey: [KEY, "reg-dash"], queryFn: api.regDashboard });
export const useRegEcl = () => useMutation({ mutationFn: api.regEcl });
export const useRegRwa = () => useMutation({ mutationFn: api.regRwa });

// M4 Economic
export const useEconIndicators = () => useQuery({ queryKey: [KEY, "econ-ind"], queryFn: api.econIndicators });
export const useEconScenarios = () => useQuery({ queryKey: [KEY, "econ-scen"], queryFn: api.econList });
export const useEconSeed = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.econSeed,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "econ-ind"] }) });
};
export const useEconGenerate = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.econGenerate,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "econ-scen"] }) });
};
export const useEconPropagate = () => useMutation({ mutationFn: api.econPropagate });

// M5 ESG
export const useEsgPortfolio = () => useQuery({ queryKey: [KEY, "esg-portfolio"], queryFn: api.esgPortfolio });
export const useEsgList = () => useQuery({ queryKey: [KEY, "esg-list"], queryFn: api.esgList });
export const useEsgAssess = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.esgAssess,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "esg-list"] }) });
};
export const useEsgClimate = () => useMutation({ mutationFn: api.esgClimate });

// M6 Market
export const useMarketDashboard = () => useQuery({ queryKey: [KEY, "market-dash"], queryFn: api.marketDashboard });
export const useMarketNews = () => useQuery({ queryKey: [KEY, "market-news"], queryFn: api.marketNews });
export const useMarketSeed = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.marketSeed,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "market-dash"] }) });
};
export const useMarketAddNews = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.marketAddNews,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "market-news"] }) });
};

// M7 Alt-Data
export const useAltIngest = () => useMutation({ mutationFn: api.altIngest });
export const useAltComposite = () => useMutation({ mutationFn: api.altComposite });

// M8 Forecasting
export const useForecastTypes = () => useQuery({ queryKey: [KEY, "forecast-types"], queryFn: api.forecastTypes });
export const useForecastList = () => useQuery({ queryKey: [KEY, "forecast-list"], queryFn: api.forecastList });
export const useForecastRun = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.forecastRun,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "forecast-list"] }) });
};

// M9 Quant
export const useQuantList = () => useQuery({ queryKey: [KEY, "quant-list"], queryFn: api.quantList });
export const useQuantVar = () => useMutation({ mutationFn: api.quantVar });
export const useQuantMonteCarlo = () => useMutation({ mutationFn: api.quantMonteCarlo });
export const useQuantStress = () => useMutation({ mutationFn: api.quantStress });

// M10 Benchmarking
export const useBenchmarkList = () => useQuery({ queryKey: [KEY, "bench-list"], queryFn: api.benchmarkList });
export const useBenchmarkRun = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.benchmarkRun,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "bench-list"] }) });
};

// M11 Executive
export const useExecPersonas = () => useQuery({ queryKey: [KEY, "personas"], queryFn: api.execPersonas });
export const useExecDashboard = () => useMutation({ mutationFn: api.execDashboard });

// M12 Optimization
export const useOptList = () => useQuery({ queryKey: [KEY, "opt-list"], queryFn: api.optList });
export const useOptLoanPricing = () => useMutation({ mutationFn: api.optLoanPricing });
export const useOptCreditLimit = () => useMutation({ mutationFn: api.optCreditLimit });

// M13 Digital Twin
export const useTwins = () => useQuery({ queryKey: [KEY, "twins"], queryFn: api.twinList });
export const useTwinCreate = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.twinCreate,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "twins"] }) });
};
export const useTwinSimulate = () => useMutation({ mutationFn: (v: { id: number; body: any }) => api.twinSimulate(v.id, v.body) });

// M14 Strategic
export const useStrategicList = () => useQuery({ queryKey: [KEY, "strategic-list"], queryFn: api.strategicList });
export const useStrategicGenerate = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: api.strategicGenerate,
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY, "strategic-list"] }) });
};
