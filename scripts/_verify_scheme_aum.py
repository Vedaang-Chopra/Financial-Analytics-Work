import pandas as pd

df = pd.read_excel("/tmp/average-aum.xlsx", header=None)
print("TITLE ROW:", repr(str(df.iloc[0, 0])))

# independent ground-truth checks (public AUM knowledge):
# PPFAS total, SBI Nifty 50 ETF, ICICI total under lakh-vs-crore hypothesis
vals = {
    "PPFAS MF total": 15_232_816,
    "SBI Nifty 50 ETF": 21_078_307,
    "ICICI MF total": 111_454_413,
}
print("\nunit hypothesis check:")
for k, v in vals.items():
    print(f"  {k}: raw={v:,}  ->as-lakh=Rs.{v/100:,.0f} cr  ->as-crore=Rs.{v:,.0f} cr")
