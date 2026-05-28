import { Homepage } from "../homepage";

type DebugFlowPageProps = React.ComponentProps<typeof Homepage>;

export function DebugFlowPage(props: DebugFlowPageProps) {
  return <Homepage {...props} />;
}
