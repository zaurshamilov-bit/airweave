import { useNavigate } from "react-router-dom";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Eye } from "lucide-react";

interface WhiteLabelIntegration {
  id: string;
  name: string;
  frontendUrl: string;
  createdAt: string;
}

interface WhiteLabelTableProps {
  integrations: WhiteLabelIntegration[];
}

export const WhiteLabelTable = ({ integrations }: WhiteLabelTableProps) => {
  const navigate = useNavigate();

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Integration ID</TableHead>
          <TableHead>Frontend URL</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="w-[100px]">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {integrations.map((integration) => (
          <TableRow 
            key={integration.id}
            className="cursor-pointer hover:bg-muted/50"
            onClick={() => navigate(`/white-label/${integration.id}`)}
          >
            <TableCell className="font-medium">{integration.name}</TableCell>
            <TableCell>{integration.id}</TableCell>
            <TableCell>{integration.frontendUrl}</TableCell>
            <TableCell>{new Date(integration.createdAt).toLocaleDateString()}</TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/white-label/${integration.id}`);
                }}
              >
                <Eye className="h-4 w-4" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};