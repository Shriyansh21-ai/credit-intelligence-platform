import { useQuery } from "@tanstack/react-query";

import * as api from "./api";

export const useOperations = () =>
  useQuery({ queryKey: ["ops", "operations"], queryFn: api.getOperations });

export const useAdmin = () =>
  useQuery({ queryKey: ["ops", "admin"], queryFn: api.getAdmin, retry: false });

export const useAnalyst = () =>
  useQuery({ queryKey: ["ops", "analyst"], queryFn: api.getAnalyst });

export const useManager = () =>
  useQuery({ queryKey: ["ops", "manager"], queryFn: api.getManager, retry: false });

export const usePortfolioOps = () =>
  useQuery({ queryKey: ["ops", "portfolio"], queryFn: api.getPortfolio });

export const useCompliance = () =>
  useQuery({ queryKey: ["ops", "compliance"], queryFn: api.getCompliance, retry: false });

export const useMonitoringOps = () =>
  useQuery({ queryKey: ["ops", "monitoring"], queryFn: api.getMonitoring });

export const useMyAccess = () =>
  useQuery({ queryKey: ["ops", "me"], queryFn: api.getMyAccess, retry: false });
